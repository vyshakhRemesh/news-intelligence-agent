from datetime import datetime
from sqlalchemy import String,Text,DateTime
from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column

class Base(DeclarativeBase):
    pass
class RawArticles(Base):
    __tablename__="raw_articles"
    id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True)
    title:Mapped[str]=mapped_column(String(500),nullable=False)
    author:Mapped[str]=mapped_column(String(225),nullable=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=True)
    description:Mapped[str]=mapped_column(Text,nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source_type: Mapped[str] = mapped_column(
    String(20),
    nullable=True
)

    def __repr__(self)->str:
        return f"<RawArticle(title={self.title[:30]}...,source={self.source_name})>"