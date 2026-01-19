from contextlib import asynccontextmanager
from datetime import date
from typing import Literal
from transformers import pipeline
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
import asyncio, os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import pooling


load_dotenv()

db_pool = None

def init_db_pool():
    global db_pool
    if db_pool is None:
        db_pool = pooling.MySQLConnectionPool(
            pool_name="movie_pool",
            pool_size=10,   # 동시에 유지할 커넥션 수
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            port=int(os.getenv("DB_PORT", 3306)),
            charset="utf8mb4"
        )

def get_connection():
    if db_pool is None:
        init_db_pool()
    return db_pool.get_connection()







ml_models = {}

def load_model_sync():
    return pipeline(
        "sentiment-analysis",
        model="nlptown/bert-base-multilingual-uncased-sentiment"
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db_pool()
    ml_models["sentiment"] = await asyncio.to_thread(load_model_sync)
    yield
    ml_models.clear()

app = FastAPI(title="영화 리뷰 사이트", lifespan=lifespan)


class ReviewRequest(BaseModel):
    text: str = Field(min_length=3, max_length=100)
    author: str = Field(min_length=3, max_length=100)
    movie_name : str

    @field_validator("text", "author")
    @classmethod
    def normalize_director(cls, v: str):
        return v.strip()



class ReviewRepository:

    @classmethod
    def delete_review(cls, review_id: int):
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM reviews WHERE id = %s",
            (review_id,)
        )
        conn.commit()

        deleted = cursor.rowcount > 0

        cursor.close()
        conn.close()

        return deleted

    @classmethod
    def get_reviews(cls, movie_name: str):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT r.id, r.author, r.text,
                   r.sentiment_label, r.sentiment_score
            FROM reviews r
            JOIN movies m ON r.movie_id = m.id
            WHERE m.title = %s
            """,
            (movie_name,)
        )

        reviews = cursor.fetchall()

        cursor.close()
        conn.close()

        return reviews

    @classmethod
    def create_review(cls, review: dict):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # 1️⃣ 영화 id 조회
        cursor.execute(
            "SELECT id FROM movies WHERE title = %s",
            (review["movie_name"],)
        )
        movie = cursor.fetchone()

        if not movie:
            raise HTTPException(
                status_code=404,
                detail="존재하지 않는 영화입니다."
            )

        movie_id = movie["id"]

        # 2️⃣ 리뷰 저장
        cursor.execute(
            """
            INSERT INTO reviews
            (movie_id, author, text, sentiment_label, sentiment_score)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                movie_id,
                review["author"],
                review["text"],
                review["sentiment_label"],
                review["sentiment_score"],
            )
        )

        conn.commit()

        new_review = {
            "id": cursor.lastrowid,
            **review
        }

        cursor.close()
        conn.close()

        return new_review





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



class MovieRepository:
    @classmethod
    def del_movie(cls, movie_title: str):
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM movies WHERE title = %s",
            (movie_title,)
        )
        conn.commit()

        deleted = cursor.rowcount > 0

        cursor.close()
        conn.close()

        return deleted
    @classmethod
    def get_movie(cls, movie_title: str):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM movies WHERE title = %s",
            (movie_title,)
        )
        movie = cursor.fetchone()

        cursor.close()
        conn.close()

        return movie

    @classmethod
    def get_movies(cls):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM movies")
        movies = cursor.fetchall()

        cursor.close()
        conn.close()

        return movies

    @classmethod
    def create_movie(cls, movie_data: dict):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                INSERT INTO movies (title, release_date, director, genre, poster_url)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    movie_data["title"],
                    movie_data["release_date"],
                    movie_data["director"],
                    movie_data["genre"],
                    movie_data["posterURL"],
                )
            )
            conn.commit()

            return {
                "id": cursor.lastrowid,
                **movie_data
            }

        except mysql.connector.IntegrityError:
            raise HTTPException(
                status_code=409,
                detail="이미 존재하는 영화입니다."
            )
        finally:
            cursor.close()
            conn.close()

# 영화 등록
@app.post("/register/movie")
def register_movie(request: MovieRequest):
    return MovieRepository.create_movie(request.model_dump())

# 모든 영화 조회
@app.get("/getallmovies")
def get_all_movies():
    return MovieRepository.get_movies()

@app.get("/getmovie")
def get_movie(movie_name: str):
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