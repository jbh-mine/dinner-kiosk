"""
MyBatis-style SQL Mapper for Python/PostgreSQL
XML 파일에서 SQL문을 로드하고 ID로 관리합니다.

사용법:
    from backend.mapper import sql

    # 단순 조회
    sql.query(conn, "helpers.selectRestaurants")

    # 파라미터 포함 조회
    sql.query(conn, "admin.selectMemberById", (mid,))

    # 단일 행 조회
    sql.query_one(conn, "helpers.selectDeadlineSettings")

    # INSERT/UPDATE/DELETE 실행
    sql.execute(conn, "admin.insertOrg", (name, parent_id, so))

    # INSERT RETURNING id
    new_id = sql.insert(conn, "admin.insertOrg", (name, parent_id, so))

    # 동적 SQL (조건절 포함)
    sql.get("admin.selectOrders")  # SQL 문자열만 반환
"""
from backend.mapper.sql_mapper import SqlMapper

# 싱글톤 매퍼 인스턴스
sql = SqlMapper()
