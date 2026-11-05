import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.middleware import CSRF_COOKIE, CSRF_HEADER
from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models.base import Base
from app.models.school import School
from app.models.user import User

PASSWORD = "correct horse battery staple"


class SchoolsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

        def override_get_db():
            with Session(self.engine) as db:
                yield db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app, base_url="https://testserver")

        self.db.add_all(
            [
                School(code="bge", name="Braeburn Garden Estate", curricula=["ib", "igcse"]),
                School(code="bs", name="Braeburn School", curricula=["igcse", "a-level"]),
                School(code="old", name="Archived School", curricula=["ib"], is_active=False),
            ]
        )
        self.db.commit()

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_db, None)
        self.db.close()
        self.engine.dispose()

    def csrf(self) -> dict[str, str]:
        if CSRF_COOKIE not in self.client.cookies:
            self.client.get("/health")
        return {CSRF_HEADER: self.client.cookies[CSRF_COOKIE]}

    def sign_in(self, role: str = "user") -> None:
        email = f"{role}@example.org"
        self.db.add(
            User(
                email=email,
                role=role,
                is_active=True,
                failed_login_attempts=0,
                password_hash=hash_password(PASSWORD),
            )
        )
        self.db.commit()
        response = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": PASSWORD},
            headers=self.csrf(),
        )
        self.assertEqual(response.status_code, 200, response.text)

    def codes(self, response) -> list[str]:
        self.assertEqual(response.status_code, 200, response.text)
        return [s["code"] for s in response.json()]


class ListSchoolsTests(SchoolsTestCase):
    def test_requires_sign_in(self) -> None:
        self.assertEqual(self.client.get("/api/schools").status_code, 401)

    def test_lists_active_schools_by_name(self) -> None:
        self.sign_in()
        response = self.client.get("/api/schools")
        self.assertEqual(self.codes(response), ["bge", "bs"])
        self.assertEqual(
            response.json()[0],
            {
                "code": "bge",
                "name": "Braeburn Garden Estate",
                "curricula": ["ib", "igcse"],
                "is_active": True,
            },
        )

    def test_filters_by_curriculum(self) -> None:
        self.sign_in()
        self.assertEqual(self.codes(self.client.get("/api/schools?curriculum=ib")), ["bge"])
        self.assertEqual(
            self.codes(self.client.get("/api/schools?curriculum=igcse")), ["bge", "bs"]
        )

    def test_rejects_unknown_curriculum(self) -> None:
        self.sign_in()
        self.assertEqual(self.client.get("/api/schools?curriculum=sat").status_code, 422)

    def test_inactive_schools_only_for_admins(self) -> None:
        self.sign_in()
        self.assertEqual(
            self.codes(self.client.get("/api/schools?include_inactive=true")), ["bge", "bs"]
        )

    def test_admin_can_include_inactive(self) -> None:
        self.sign_in("admin")
        self.assertEqual(
            self.codes(self.client.get("/api/schools?include_inactive=true")),
            ["old", "bge", "bs"],
        )


class ManageSchoolsTests(SchoolsTestCase):
    def test_non_admin_cannot_create(self) -> None:
        self.sign_in()
        response = self.client.post(
            "/api/schools",
            json={"code": "new", "name": "New", "curricula": ["ib"]},
            headers=self.csrf(),
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_creates_with_normalised_values(self) -> None:
        self.sign_in("admin")
        response = self.client.post(
            "/api/schools",
            json={"code": " Nairobi-1 ", "name": "Nairobi", "curricula": ["IB", "ib", "A-Level"]},
            headers=self.csrf(),
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["code"], "nairobi-1")
        self.assertEqual(response.json()["curricula"], ["ib", "a-level"])

    def test_duplicate_code_conflicts(self) -> None:
        self.sign_in("admin")
        response = self.client.post(
            "/api/schools", json={"code": "BGE", "name": "Dup"}, headers=self.csrf()
        )
        self.assertEqual(response.status_code, 409)

    def test_rejects_invalid_values(self) -> None:
        self.sign_in("admin")
        for body in (
            {"code": "all", "name": "Reserved"},
            {"code": "has space", "name": "Bad code"},
            {"code": "-x", "name": "Bad code"},
            {"code": "ok", "name": "Bad curriculum", "curricula": ["sat"]},
            {"code": "ok", "name": ""},
        ):
            with self.subTest(body=body):
                response = self.client.post("/api/schools", json=body, headers=self.csrf())
                self.assertEqual(response.status_code, 422)

    def test_admin_updates_school(self) -> None:
        self.sign_in("admin")
        response = self.client.patch(
            "/api/schools/BGE",
            json={"curricula": ["ib", "igcse", "a-level"], "is_active": False},
            headers=self.csrf(),
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["curricula"], ["ib", "igcse", "a-level"])
        self.assertFalse(response.json()["is_active"])

    def test_update_rejects_null_and_unknown(self) -> None:
        self.sign_in("admin")
        null = self.client.patch("/api/schools/bge", json={"name": None}, headers=self.csrf())
        self.assertEqual(null.status_code, 422)
        missing = self.client.patch("/api/schools/nope", json={"name": "X"}, headers=self.csrf())
        self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()
