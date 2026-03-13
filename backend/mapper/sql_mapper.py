"""
MyBatis-style SQL Mapper Engine
XML 파일에서 SQL 쿼리를 파싱하고 namespace.id 형식으로 관리합니다.
"""
import os
import xml.etree.ElementTree as ET
from psycopg2.extras import RealDictCursor


class SqlMapper:
    """XML 기반 SQL 매퍼 - MyBatis 스타일"""

    def __init__(self):
        self._queries = {}   # { "namespace.id": sql_text }
        self._loaded = False

    def load(self, xml_dir: str = None):
        """XML 매퍼 파일 로드 (초초 1회 자동 호출)"""
        if self._loaded:
            return
        if xml_dir is None:
            xml_dir = os.path.join(os.path.dirname(__file__), "xml")
        if not os.path.isdir(xml_dir):
            raise FileNotFoundError(f"Mapper XML directory not found: {xml_dir}")

        for fname in sorted(os.listdir(xml_dir)):
            if not fname.endswith(".xml"):
                continue
            fpath = os.path.join(xml_dir, fname)
            self._parse_xml(fpath)

        self._loaded = True
        print(f"[SqlMapper] {len(self._queries)} queries loaded from {xml_dir}")

    def _parse_xml(self, filepath: str):
        """/개별 XML 파일 파싱"""
        tree = ET.parse(filepath)
        root = tree.getroot()
        namespace = root.attrib.get("namespace", "")

        for tag in ("select", "insert", "update", "delete"):
            for elem in root.iter(tag):
                qid = elem.attrib.get("id", "")
                if not qid:
                    continue
                full_id = f"{namespace}.{qid}" if namespace else qid
                sql_text = self._extract_sql(elem)
                self._queries[full_id] = sql_text.strip()

    def _extract_sql(self, elem) -> str:
        """XML 요소에서 SQL 텍스트 추출 (동적 SQL 태그 포함)"""
        parts = []
        if elem.text:
            parts.append(elem.text)
        for child in elem:
            if child.tag == "if":
                test = child.attrib.get("test", "")
                inner_sql = self._extract_sql(child)
                parts.append(f"/* if: {test} */ {inner_sql} /* end if */")
            elif child.tag == "where":
                inner_sql = self._extract_sql(child)
                parts.append(f"WHERE {inner_sql}")
            elif child.tag == "include":
                ref_id = child.attrib.get("refid", "")
                if ref_id in self._queries:
                    parts.append(self._queries[ref_id])
            else:
                if child.text:
                    parts.append(child.text)
            if child.tail:
                parts.append(child.tail)
        return " ".join(parts)

    def _ensure_loaded(self):
        if not self._loaded:
            self.load()

    def get(self, query_id: str) -> str:
        """SQL 문자열 반환 (동적 SQL 구성 시 사용)"""
        self._ensure_loaded()
        if query_id not in self._queries:
            raise KeyError(f"SQL query not found: '{query_id}'")
        return self._queries[query_id]

    def query(self, conn, query_id: str, params=None) -> list:
        """SELECT 실행 → list[dict] 반환"""
        sql = self.get(query_id)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        cur.close()
        return rows

    def query_one(self, conn, query_id: str, params=None) -> dict:
        """SELECT 실행 → 단일 dict 반환 (없으면 None)"""
        sql = self.get(query_id)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params or ())
        row = cur.fetchone()
        cur.close()
        return row

    def query_scalar(self, conn, query_id: str, params=None, key: str = None):
        """SELECT 실행 → 단일 스칼라 값 반환"""
        row = self.query_one(conn, query_id, params)
        if row is None:
            return None
        if key:
            return row[key]
        return list(row.values())[0]

    def execute(self, conn, query_id: str, params=None) -> int:
        """INSERT/UPDATE/DELETE 실행 → 영향받은 행 수 반환"""
        sql = self.get(query_id)
        cur = conn.cursor()
        cur.execute(sql, params or ())
        rowcount = cur.rowcount
        cur.close()
        return rowcount

    def insert(self, conn, query_id: str, params=None) -> int:
        """INSERT ... RETURNING id 실행 → 새 ID 반환"""
        sql = self.get(query_id)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params or ())
        row = cur.fetchone()
        cur.close()
        return row["id"] if row else None

    def execute_raw(self, conn, sql: str, params=None) -> int:
        """\uc6d0시 SQL 직접 실행 (동적 SQL 등)"""
        cur = conn.cursor()
        cur.execute(sql, params or ())
        rowcount = cur.rowcount
        cur.close()
        return rowcount

    def query_raw(self, conn, sql: str, params=None) -> list:
        """\uc6d0시 SQL 직접 조회 (동적 SQL 등)"""
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        cur.close()
        return rows

    def query_one_raw(self, conn, sql: str, params=None) -> dict:
        """\uc6d0시 SQL 단일 행 조회"""
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params or ())
        row = cur.fetchone()
        cur.close()
        return row

    def list_queries(self, namespace: str = None) -> list:
        """\ub4f1록된 쿼리 ID 목록 반환 (디버깅용)"""
        self._ensure_loaded()
        if namespace:
            return [k for k in sorted(self._queries.keys()) if k.startswith(namespace + ".")]
        return sorted(self._queries.keys())
