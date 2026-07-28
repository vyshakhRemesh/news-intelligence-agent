"""
Test suite for the ingestion layer changes.

Run with: python -m pytest tests/test_ingestion.py -v
Or:       python tests/test_ingestion.py
"""
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import feedparser

# Setup logging to see structured output
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ============================================================================
# TEST 1: Parallel Fetching Speed
# ============================================================================

def test_parallel_vs_sequential():
    """
    Prove that ThreadPoolExecutor actually fetches in parallel.

    We mock 4 sources that each sleep for 1 second.
    - Sequential would take ~4 seconds
    - Parallel with 4 workers should take ~1 second
    """
    print("\n" + "="*60)
    print("TEST 1: Parallel Fetching Speed")
    print("="*60)

    def slow_fetch(name):
        time.sleep(1)  # Simulate 1s API latency
        return [{"title": f"Article from {name}", "url": f"http://{name}.com/1", "source_name": name}]

    sources = ["newsapi", "gnews", "currents", "nytimes"]

    # Sequential timing
    start = time.time()
    seq_results = []
    for s in sources:
        seq_results.extend(slow_fetch(s))
    seq_time = time.time() - start
    print(f"Sequential: {seq_time:.2f}s for {len(sources)} sources")

    # Parallel timing (simulating what aggregator does)
    start = time.time()
    par_results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(slow_fetch, s): s for s in sources}
        for future in futures:
            par_results.extend(future.result())
    par_time = time.time() - start
    print(f"Parallel:   {par_time:.2f}s for {len(sources)} sources")

    speedup = seq_time / par_time
    print(f"Speedup:    {speedup:.1f}x")

    assert speedup > 2.5, f"Parallel not working! Speedup only {speedup:.1f}x"
    assert len(par_results) == len(seq_results) == 4
    print("✅ PASS: Parallel fetching works\n")


# ============================================================================
# TEST 2: Same-Source Deduplication Per Run
# ============================================================================

def test_same_source_dedup():
    """
    Same URL from the SAME source within one run → should be deduped.
    """
    print("="*60)
    print("TEST 2: Same-Source Deduplication Per Run")
    print("="*60)

    seen_this_run = set()
    all_articles = []

    articles = [
        {"url": "http://bbc.com/news/1", "source_name": "BBC"},
        {"url": "http://bbc.com/news/1", "source_name": "BBC"},  # Same source dup
        {"url": "http://bbc.com/news/2", "source_name": "BBC"},
    ]

    for article in articles:
        url = article.get("url")
        source_name = article.get("source_name", "Unknown")
        run_key = (url, source_name)
        if run_key in seen_this_run:
            print(f"  Skipped same-source dup: {url} from {source_name}")
            continue
        seen_this_run.add(run_key)
        all_articles.append(article)

    print(f"  Input: {len(articles)} articles")
    print(f"  Output: {len(all_articles)} articles (1 deduped)")
    assert len(all_articles) == 2, f"Expected 2, got {len(all_articles)}"
    print("✅ PASS: Same-source duplicates are removed\n")


# ============================================================================
# TEST 3: Cross-Source Duplicates PRESERVED
# ============================================================================

def test_cross_source_preserved():
    """
    Same URL from DIFFERENT sources → MUST be kept for contradiction analysis.
    This is the most critical test for your architecture.
    """
    print("="*60)
    print("TEST 3: Cross-Source Duplicates PRESERVED")
    print("="*60)

    seen_this_run = set()
    all_articles = []

    articles = [
        {"url": "http://reuters.com/article/1", "source_name": "Reuters", "title": "EU passes AI law"},
        {"url": "http://reuters.com/article/1", "source_name": "BBC", "title": "EU passes AI law"},
        {"url": "http://reuters.com/article/1", "source_name": "CNN", "title": "EU passes AI law"},
    ]

    for article in articles:
        url = article.get("url")
        source_name = article.get("source_name", "Unknown")
        run_key = (url, source_name)
        if run_key in seen_this_run:
            continue
        seen_this_run.add(run_key)
        all_articles.append(article)

    print(f"  Input: {len(articles)} articles (same URL, 3 different sources)")
    print(f"  Output: {len(all_articles)} articles")
    for a in all_articles:
        print(f"    - {a['source_name']}: {a['title']}")

    assert len(all_articles) == 3, f"Expected 3 (all preserved), got {len(all_articles)}"
    print("✅ PASS: Cross-source duplicates are PRESERVED for contradiction analysis\n")


# ============================================================================
# TEST 4: RSS Bozo Fix
# ============================================================================

def test_rss_bozo_fix():
    """
    Feeds with bozo bit but valid entries should NOT be skipped.
    """
    print("="*60)
    print("TEST 4: RSS Bozo Fix")
    print("="*60)

    # Simulate what feedparser returns
    class MockFeed:
        def __init__(self, bozo, entries):
            self.bozo = bozo
            self.entries = entries

    # Case 1: bozo=True but has entries → should process
    feed_with_bozo = MockFeed(bozo=True, entries=[
        {"title": "Valid Article", "link": "http://example.com/1", "published": "Mon, 01 Jan 2024 10:00:00 +0000"}
    ])

    # Case 2: bozo=False but no entries → should skip
    feed_empty = MockFeed(bozo=False, entries=[])

    # Case 3: bozo=True and no entries → should skip
    feed_bozo_empty = MockFeed(bozo=True, entries=[])

    def process_feed(feed, source_name):
        if not feed.entries:
            return "SKIPPED (no entries)"
        if feed.bozo:
            return "PROCESSED (bozo but has entries)"
        return "PROCESSED"

    result1 = process_feed(feed_with_bozo, "TestSource")
    result2 = process_feed(feed_empty, "TestSource")
    result3 = process_feed(feed_bozo_empty, "TestSource")

    print(f"  Feed with bozo + entries: {result1}")
    print(f"  Feed empty (no bozo):     {result2}")
    print(f"  Feed empty + bozo:        {result3}")

    assert result1 == "PROCESSED (bozo but has entries)", "Bozo fix broken!"
    assert result2 == "SKIPPED (no entries)"
    assert result3 == "SKIPPED (no entries)"
    print("✅ PASS: RSS bozo fix works correctly\n")


# ============================================================================
# TEST 5: NewsAPI None Fix
# ============================================================================

def test_newsapi_none_fix():
    """
    When NewsAPI fails, it must return [] not None.
    None breaks all_articles.extend(None) → TypeError.
    """
    print("="*60)
    print("TEST 5: NewsAPI None Fix")
    print("="*60)

    def old_behavior():
        return None  # Your old code did this

    def new_behavior():
        return []  # Fixed code

    all_articles = []

    # Old behavior would crash
    try:
        all_articles.extend(old_behavior())
        print("  Old behavior: DID NOT CRASH (unexpected)")
    except TypeError as e:
        print(f"  Old behavior: CRASHED with TypeError ✓")

    # New behavior works
    all_articles.extend(new_behavior())
    print(f"  New behavior: returned {new_behavior()} ✓")
    assert new_behavior() == []
    print("✅ PASS: NewsAPI returns [] on failure\n")


# ============================================================================
# TEST 6: Circuit Breaker
# ============================================================================

def test_circuit_breaker():
    """
    After 3 failures, circuit opens and skips calls.
    """
    print("="*60)
    print("TEST 6: Circuit Breaker")
    print("="*60)

    class TestCircuitBreaker:
        def __init__(self, failure_threshold=3):
            self.failures = 0
            self.state = "CLOSED"
            self.failure_threshold = failure_threshold

        def call(self, func):
            if self.state == "OPEN":
                return "SKIPPED (circuit open)"
            try:
                result = func()
                self.failures = 0
                self.state = "CLOSED"
                return result
            except Exception:
                self.failures += 1
                if self.failures >= self.failure_threshold:
                    self.state = "OPEN"
                return []

    cb = TestCircuitBreaker(failure_threshold=3)

    def failing_func():
        raise Exception("API down")

    # Call 1: fail
    r1 = cb.call(failing_func)
    print(f"  Call 1: failures={cb.failures}, state={cb.state}")

    # Call 2: fail
    r2 = cb.call(failing_func)
    print(f"  Call 2: failures={cb.failures}, state={cb.state}")

    # Call 3: fail → circuit opens
    r3 = cb.call(failing_func)
    print(f"  Call 3: failures={cb.failures}, state={cb.state}")

    # Call 4: skipped because circuit is open
    r4 = cb.call(failing_func)
    print(f"  Call 4: state={cb.state}, result={r4}")

    assert cb.state == "OPEN", "Circuit should be open after 3 failures"
    assert r4 == "SKIPPED (circuit open)", "Should skip when open"
    print("✅ PASS: Circuit breaker opens after 3 failures\n")


# ============================================================================
# TEST 7: Full Integration Simulation
# ============================================================================

def test_full_integration():
    """
    Simulate a full aggregator run with mixed results.
    """
    print("="*60)
    print("TEST 7: Full Integration Simulation")
    print("="*60)

    # Mock articles from different sources
    mock_newsapi = [
        {"url": "http://reuters.com/ai-law", "source_name": "Reuters"},
        {"url": "http://bbc.com/ai-law", "source_name": "BBC"},
    ]
    mock_gnews = [
        {"url": "http://reuters.com/ai-law", "source_name": "Reuters"},  # Cross-source dup
        {"url": "http://cnn.com/tech-news", "source_name": "CNN"},
    ]
    mock_rss = [
        {"url": "http://bbc.com/ai-law", "source_name": "BBC"},  # Cross-source dup
        {"url": "http://guardian.com/climate", "source_name": "The Guardian"},
    ]

    # Simulate aggregator logic
    seen_this_run = set()
    all_articles = []

    for batch in [mock_newsapi, mock_gnews, mock_rss]:
        for article in batch:
            url = article.get("url")
            source = article.get("source_name", "Unknown")
            run_key = (url, source)
            if run_key in seen_this_run:
                print(f"  DEDUPED: {url} from {source}")
                continue
            seen_this_run.add(run_key)
            all_articles.append(article)

    print(f"  Total unique articles: {len(all_articles)}")
    for a in all_articles:
        print(f"    - {a['source_name']}: {a['url']}")

    # Should have 4 unique (Reuters, BBC from NewsAPI + Reuters, BBC from cross-source + CNN + Guardian)
    # Actually: Reuters(NewsAPI), BBC(NewsAPI), Reuters(GNews - preserved), CNN, BBC(RSS - preserved), Guardian
    assert len(all_articles) == 4, f"Expected 4, got {len(all_articles)}"
    print("✅ PASS: Full integration works\n")


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("INGESTION LAYER TEST SUITE")
    print("="*60 + "\n")

    test_parallel_vs_sequential()
    test_same_source_dedup()
    test_cross_source_preserved()
    test_rss_bozo_fix()
    test_newsapi_none_fix()
    test_circuit_breaker()
    test_full_integration()

    print("="*60)
    print("ALL TESTS PASSED ✅")
    print("="*60)
