import streamlit as st
import requests
from datetime import date

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="🎬 영화 리뷰 사이트", layout="centered")
st.title("🎬 영화 리뷰 사이트")

# ===============================
# ✅ session_state (단 하나!)
# ===============================
if "page" not in st.session_state:
    st.session_state.page = "전체 영화 조회"

if "search_title" not in st.session_state:
    st.session_state.search_title = ""

# ===============================
# ✅ 사이드바 (표시용만)
# ===============================
sidebar_page = st.sidebar.selectbox(
    "메뉴",
    ["영화 등록", "전체 영화 조회", "영화 검색", "영화 삭제"],
    index=["영화 등록", "전체 영화 조회", "영화 검색", "영화 삭제"]
    .index(st.session_state.page)
)

# 사이드바를 사용자가 바꿨을 때만 반영
if sidebar_page != st.session_state.page:
    st.session_state.page = sidebar_page
    st.rerun()

page = st.session_state.page

# ===============================
# 🎥 영화 등록
# ===============================
if page == "영화 등록":
    st.subheader("🎥 영화 등록")

    title = st.text_input("영화 제목")
    release_date = st.date_input("개봉일", value=date.today())
    director = st.text_input("감독")
    genre = st.selectbox("장르", ["SF", "Drama", "Action", "Comedy"])
    posterURL = st.text_input("포스터 URL (namu.wiki)")

    if st.button("등록"):
        payload = {
            "title": title,
            "release_date": str(release_date),
            "director": director,
            "genre": genre,
            "posterURL": posterURL
        }

        res = requests.post(f"{API_BASE}/register/movie", json=payload)

        if res.status_code == 200:
            st.success("🎉 영화 등록 성공!")
        else:
            st.error(res.json().get("detail", "오류 발생"))

# ===============================
# 📃 전체 영화 조회
# ===============================
elif page == "전체 영화 조회":
    st.subheader("📃 전체 영화 목록")

    res = requests.get(f"{API_BASE}/getallmovies")
    movies = res.json() if res.status_code == 200 else []

    if not movies:
        st.info("등록된 영화가 없습니다.")
    else:
        for movie in movies:
            col1, col2 = st.columns([4, 1])

            with col1:
                st.markdown(f"### 🎬 {movie['title']}")
                st.write(f"🎞 개봉일: {movie['release_date']}")
                st.write(f"🎬 감독: {movie['director']}")
                st.write(f"🎭 장르: {movie['genre']}")

            with col2:
                if st.button("🔍 보기", key=f"view_{movie['id']}"):
                    st.session_state.search_title = movie["title"]
                    st.session_state.page = "영화 검색"
                    st.rerun()

            st.divider()

# ===============================
# 🔍 영화 검색 + 리뷰
# ===============================
elif page == "영화 검색":
    st.subheader("🔍 영화 검색")

    title = st.text_input("영화 제목", value=st.session_state.search_title)

    if not title:
        st.stop()

    res = requests.get(
        f"{API_BASE}/getmovie",
        params={"movie_name": title}
    )

    if res.status_code != 200:
        st.error("영화를 찾을 수 없습니다.")
        st.stop()

    movie = res.json()

    st.markdown(f"## 🎬 {movie['title']}")

    if movie["posterURL"]:
        st.image(movie["posterURL"], width = 300)
    else:
        st.info("포스터 이미지가 없습니다.")


    st.write(f"📅 개봉일: {movie['release_date']}")
    st.write(f"🎬 감독: {movie['director']}")
    st.write(f"🎭 장르: {movie['genre']}")

    st.divider()

    # ===============================
    # ✍️ 리뷰 작성 (위)
    # ===============================
    st.markdown("## ✍️ 리뷰 작성")

    with st.form("review_form"):
        author = st.text_input("작성자")
        text = st.text_area("리뷰 내용")
        submitted = st.form_submit_button("리뷰 등록")

        if submitted:
            payload = {
                "author": author,
                "text": text,
                "movie_name": movie["title"]
            }

            res = requests.post(f"{API_BASE}/register/review", json=payload)

            if res.status_code == 200:
                st.success("리뷰 등록 완료!")
                st.rerun()
            else:
                st.error(res.json().get("detail", "리뷰 등록 실패"))

    st.divider()

    # ===============================
    # 📝 리뷰 목록 (아래)
    # ===============================
    st.markdown("## 📝 리뷰 목록")

    review_res = requests.get(
        f"{API_BASE}/reviews",
        params={"movie_name": movie["title"]}
    )

    reviews = review_res.json() if review_res.status_code == 200 else []

    if not reviews:
        st.info("아직 리뷰가 없습니다.")
    else:
        for r in reviews:
            col1, col2 = st.columns([4, 1])

            with col1:
                st.markdown(f"**✍️ {r['author']}**")
                st.write(r["text"])

                # ===============================
                # 😊 감성 분석 결과 표시
                # ===============================
                sentiment_label = r.get("sentiment_label")
                sentiment_score = r.get("sentiment_score")

                if sentiment_label and sentiment_score is not None:
                    # 별점 숫자만 추출 (예: "4 stars" → 4)
                    stars = int(sentiment_label.split()[0])

                    st.markdown(
                        f"⭐ 감성 점수: **{stars} / 5**  "
                        f"(신뢰도: {sentiment_score:.2f})"
                    )

                    # 시각적으로 조금 더 예쁘게
                    st.progress(stars / 5)

            with col2:
                if st.button("🗑 삭제", key=f"del_{r['id']}"):
                    del_res = requests.delete(
                        f"{API_BASE}/delreview",
                        params={"review_id": r["id"]}
                    )

                    if del_res.status_code == 200:
                        st.success("리뷰 삭제 완료")
                        st.rerun()
                    else:
                        st.error("리뷰 삭제 실패")

            st.divider()

# ===============================
# 🗑 영화 삭제
# ===============================
elif page == "영화 삭제":
    st.subheader("🗑 영화 삭제")

    movie_name = st.text_input("삭제할 영화 제목")

    if st.button("삭제"):
        res = requests.delete(
            f"{API_BASE}/delmovie",
            params={"movie_name": movie_name}
        )

        if res.status_code == 200:
            st.success("🧹 영화 삭제 완료!")
        else:
            st.error(res.json().get("detail", "삭제 실패"))