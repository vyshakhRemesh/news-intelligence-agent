"""
User Interest Module

Matches article topic against user interests.
"""


class UserInterest:

    @staticmethod
    def calculate(article, user):

        topic = getattr(article, "primary_topic", None)

        if topic is None:
            return 50

        topic = topic.lower()

        interests = [
            x.lower()
            for x in user["preferred_topics"]
        ]

        if topic in interests:
            return 100

        return 40