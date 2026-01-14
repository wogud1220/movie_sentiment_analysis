from contextlib import asynccontextmanager
from datetime import date
from typing import Literal
import time
from transformers import pipeline
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
import asyncio



ml_models = {}

def load_model_sync():
    return pipeline(
        "sentiment-analysis",
        model="nlptown/bert-base-multilingual-uncased-sentiment"
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    ml_models["sentiment"] = await asyncio.to_thread(load_model_sync)
    yield
    ml_models.clear()

app = FastAPI(title="영화 리뷰 사이트", lifespan=lifespan)


class ReviewRequest(BaseModel):
    text: str = Field(min_length=3, max_length=100)
    author: str = Field(min_length=3, max_length=100)
    movie_name : str


    @field_validator("movie_name")
    @classmethod
    def validate_movie_exists(cls, v: str):
        for movie in MovieRepository.all_movies:
            if movie["title"] == v:
                return v

        raise HTTPException(
            status_code=404,
            detail="존재하지 않는 영화엔 리뷰를 작성할 수 없습니다."
        )

    @field_validator("text", "author")
    @classmethod
    def normalize_director(cls, v: str):
        return v.strip()


class ReviewRepository():
    id = 1
    reviews = []
    @classmethod
    def create_review(cls, review: dict):
        new_review = {
            "id": cls.id,
            **review
        }
        cls.reviews.append(new_review)
        cls.id += 1
        return new_review


    @classmethod
    def delete_review(cls, review_id: int):
        for review in cls.reviews:
            if review["id"] == review_id:
                cls.reviews.remove(review)
                return True
        return False

    @classmethod
    def get_reviews(cls, movie_name: str):
        return [
            r for r in cls.reviews if r["movie_name"] == movie_name
        ]


@app.get("/reviews")
def get_reviews(movie_name: str):
    return ReviewRepository.get_reviews(movie_name)

@app.post("/register/review")
def register_review(request: ReviewRequest):
        sentiment = ml_models["sentiment"](request.text)
        return ReviewRepository.create_review({
                "text": request.text,
                "author": request.author,
                "movie_name": request.movie_name,
                "sentiment_label": sentiment[0]["label"],
                "sentiment_score": sentiment[0]["score"],
        })

@app.delete("/delreview")
def delete_review(review_id: int):
    success_del = ReviewRepository.delete_review(review_id)
    if success_del:
        return {
            "message": "해당 리뷰 삭제 성공.",
        }
    else:
        raise HTTPException(
            status_code=404,
            detail="삭제할 리뷰가 존재하지 않습니다."
        )














class MovieRequest(BaseModel):
    title: str = Field(min_length=1, max_length=30)
    release_date: date
    director: str = Field(min_length=1, max_length=30)
    genre: Literal["SF", "Drama", "Action", "Comedy"]
    posterURL: str = Field(pattern=r"^https://i.namu\.wiki/.+",)


    @field_validator("title", "director")
    @classmethod
    def make_lower(cls,v:str):
        return v.strip().lower()

    @field_validator("posterURL")
    @classmethod
    def normalize_director(cls, v: str):
        return v.strip()


class MovieRepository():
    id = 1
    all_movies = []

    # 영화 등록
    @classmethod
    def create_movie(cls, movie_data: dict):
        for movie in cls.all_movies:
            if movie_data["title"] == movie["title"]:
                raise HTTPException(
                    status_code=409,
                    detail="이미 존재하는 영화입니다."
                )

        new_movie = {
            "id": cls.id,
            **movie_data,
        }
        cls.all_movies.append(new_movie)
        cls.id += 1
        return new_movie


    # 모든 영화 조회
    @classmethod
    def get_movies(cls):
        return cls.all_movies


    # 특정 영화 조회
    @classmethod
    def get_movie(cls, movie_title: str):
        for movie in cls.all_movies:
            if movie["title"] == movie_title:
                return movie
        return None

    @classmethod
    def del_movie(cls, movie_title: str):
        for movie in cls.all_movies:
            if movie["title"] == movie_title:
                cls.all_movies.remove(movie)
                return True
        return False




#영화 등록
@app.post("/register/movie")
def register_movie(request: MovieRequest):
    return MovieRepository.create_movie(request.model_dump())

# 모든 영화 조회
@app.get("/getallmovies")
def get_all_movies():
    return MovieRepository.get_movies()

@app.get("/getmovie")
def get_movie(movie_name:str):
    movie = MovieRepository.get_movie(movie_name)
    if movie is None:
        raise HTTPException(
            status_code=404,
            detail="해당 영화 제목은 존재하지 않습니다."
        )
    return movie


@app.delete("/delmovie")
def del_movie(movie_name: str):
    success_del = MovieRepository.del_movie(movie_name)
    if success_del:
        return {
            "message": "삭제에 성공했습니다.",
            "title": movie_name,
        }
    else:
        raise HTTPException(
            status_code=404,
            detail="삭제할 영화가 존재하지 않습니다."
        )
