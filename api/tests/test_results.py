import io
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook
from openpyxl.styles import PatternFill
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.middleware import CSRF_COOKIE, CSRF_HEADER
from app.core.security import hash_password
from app.database import get_db
from app.features.results import rules
from app.features.results.analysis import analyse
from app.features.results.matching import match_students
from app.features.results.parsers import (
    ParsedCandidate,
    ParsedCemStudent,
    WorkbookError,
    parse_cem,
    parse_ib_results,
)
from app.main import app
from app.models.base import Base
from app.models.school import School
from app.models.user import User

DOCS = Path(__file__).resolve().parents[2] / "docs"
CEM_FILE = DOCS / "CEM IBE Baseline.xlsx"
RESULTS_FILE = DOCS / "IB Results 2026.xlsx"
PASSWORD = "correct horse battery staple"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
GREEN = PatternFill("solid", fgColor="FF92D050")
YELLOW = PatternFill("solid", fgColor="FFFFFF00")


def workbook_bytes(build) -> bytes:
    book = Workbook()
    build(book.active)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def results_sheet(sheet, rows, title="IBDP"):
    sheet.title = title
    sheet.append([None, None, None, "Eng", "Fre", "Bio", "Mat", "EE", None, "TOK", "EP", "Total"])
    for row in rows:
        sheet.append(row)


@unittest.skipUnless(CEM_FILE.exists() and RESULTS_FILE.exists(), "sample workbooks missing")
class SampleWorkbookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cem = parse_cem(CEM_FILE.read_bytes())
        cls.results = parse_ib_results(RESULTS_FILE.read_bytes())
        cls.analysis = analyse([("bge", cls.results.records, cls.cem.records)])

    def test_parses_cem_baseline(self) -> None:
        self.assertEqual(self.cem.summary["students"], 52)
        self.assertEqual(self.cem.summary["predictions"], 230)
        first = self.cem.records[0]
        self.assertEqual((first.first_name, first.last_name, first.gender), ("Rahma", "Abdirahman", "F"))
        french = first.predictions[2]
        self.assertEqual((french.subject, french.level, french.variant), ("fre", "SL", "ab"))

    def test_reads_levels_from_cell_colours(self) -> None:
        self.assertEqual(self.results.summary["dp_candidates"], 32)
        self.assertEqual(self.results.summary["cp_candidates"], 22)
        aruna = self.results.records[0]
        self.assertEqual(
            [(s.subject, s.level, s.variant, s.grade) for s in aruna.subjects],
            [
                ("eng", "SL", None, 4),
                ("spa", "SL", None, 5),
                ("bus", "HL", None, 5),
                ("ess", "HL", None, 5),
                ("phy", "HL", None, 4),
                ("mat", "SL", "aa", 5),
            ],
        )
        self.assertEqual((aruna.ee_subject, aruna.ee_grade, aruna.tok_grade), ("Phy", "C", "C"))
        self.assertEqual((aruna.core_points, aruna.total_points), (1, 29))
        self.assertTrue(any("Augustin Maillard" in w for w in self.results.summary["warnings"]))

    def test_matches_report_headline_figures(self) -> None:
        dp = self.analysis["summary"]["dp"]
        self.assertEqual(dp["candidates"], 32)
        self.assertEqual(dp["diploma"]["rate"], 93.8)
        self.assertEqual(dp["diploma"]["above_40_rate"], 9.4)
        self.assertEqual(dp["diploma"]["above_35_rate"], 40.6)
        self.assertEqual(dp["diploma"]["average_points_awarded"], 34.3)
        self.assertEqual(dp["average_points"], 33.62)
        self.assertEqual(dp["grade_counts"], [0, 1, 7, 28, 70, 66, 20])
        self.assertEqual(self.analysis["summary"]["cp"]["candidates"], 21)
        self.assertEqual(self.analysis["summary"]["cp"]["average_points"], 12.38)
        self.assertEqual(self.analysis["summary"]["combined"]["average_points"], 25.21)

    def test_subject_uptake_by_level(self) -> None:
        rows = {r["label"]: r["stats"] for r in self.analysis["subjects"]}
        self.assertEqual(rows["Eng HL"]["dp"]["entries"], 18)
        self.assertEqual(rows["Eng HL"]["dp"]["uptake"], 56.2)
        self.assertEqual(rows["Mat SL AA"]["dp"]["uptake"], 62.5)
        self.assertEqual(rows["Mat SL AI"]["dp"]["entries"], 9)
        self.assertEqual(rows["Fre Ab"]["dp"]["entries"], 5)
        # Level not given by colour comes from CEM (IB-S-Chemistry).
        self.assertEqual(rows["Che SL"]["dp"]["entries"], 1)
        self.assertIsNone(rows["Bus HL"]["cp"])

    def test_withholds_diplomas_by_rule(self) -> None:
        students = {s["name"]: s for s in self.analysis["students"]}
        self.assertEqual(
            [c["code"] for c in students["Keithrogers Munene"]["failing"]], ["D1", "D2"]
        )
        self.assertEqual([c["code"] for c in students["Devam Raithatha"]["failing"]], ["D2"])
        self.assertTrue(students["Margaret Manning"]["awarded"])
        self.assertIsNone(students["Atieno Tru Kerkering"]["awarded"])
        self.assertFalse(students["Atieno Tru Kerkering"]["in_cohort"])

    def test_value_added_uses_matching_prediction(self) -> None:
        students = {s["name"]: s for s in self.analysis["students"]}
        rahama = {e["label"]: e for e in students["Rahama Abdirahman"]["subjects"]}
        self.assertEqual(rahama["Fre Ab"]["predicted"], 5.0)
        self.assertEqual(rahama["Fre Ab"]["va"], -2.0)
        # No CEM prediction for ESS, so no VA.
        self.assertIsNone({e["label"]: e for e in students["Eniss Aruna (Lwanzo)"]["subjects"]}["ESS HL"]["va"])

    def test_reports_matching(self) -> None:
        matching = self.analysis["matching"]
        self.assertEqual(matching["unmatched_results"], ["Lewis Ochola", "Nathan Tassew"])
        self.assertEqual(
            matching["review"], [{"name": "Coco Monasch", "cem_name": "Charlotte Chipo Monasch"}]
        )
        self.assertEqual(matching["unmatched_cem"], [])


class MatchingTests(unittest.TestCase):
    def test_uses_first_names_for_shared_surnames(self) -> None:
        results = [ParsedCandidate("DP", first, "Richards") for first in ("Natasha", "Jamie", "Natalie")]
        cems = [ParsedCemStudent(first, "Richards", None, None) for first in ("Natalie", "Natasha")]
        pairs = {m.result.first_name: m.cem.first_name for m in match_students(results, cems)}
        self.assertEqual(pairs, {"Natasha": "Natasha", "Natalie": "Natalie"})

    def test_tolerates_spelling_accents_and_lost_characters(self) -> None:
        results = [
            ParsedCandidate("CP", "Rahama", "Abdirahman"),
            ParsedCandidate("DP", "Jérôme-Mickaël", "Happi Mangoua"),
            ParsedCandidate("DP", "(Michael) Tyler", "Ochieng"),
        ]
        cems = [
            ParsedCemStudent("Rahma", "Abdirahman", None, None),
            ParsedCemStudent("J?r?me-Micka?l", "Happi Mangoua", None, None),
            ParsedCemStudent("Michael", "Ochieng'", None, None),
        ]
        matches = match_students(results, cems)
        self.assertEqual(len(matches), 3)
        self.assertTrue(all(m.confident for m in matches))

    def test_ambiguous_surname_only_is_not_matched(self) -> None:
        results = [ParsedCandidate("DP", "Coco", "Ali")]
        cems = [ParsedCemStudent("Nael", "Ali", None, None), ParsedCemStudent("Sam", "Ali", None, None)]
        self.assertEqual(match_students(results, cems), [])


class RuleTests(unittest.TestCase):
    def test_core_matrix(self) -> None:
        self.assertEqual(rules.core_points("A", "A"), 3)
        self.assertEqual(rules.core_points("C", "B"), 2)
        self.assertEqual(rules.core_points("D", "D"), 0)
        self.assertIsNone(rules.core_points("E", "A"))
        self.assertIsNone(rules.core_points(None, "A"))

    def test_diploma_conditions(self) -> None:
        def codes(grades, ee="B", tok="B", total=30):
            return [c.code for c in rules.diploma_conditions(grades, ee, tok, total)]

        good = [("HL", 5), ("HL", 5), ("HL", 5), ("SL", 5), ("SL", 5), ("SL", 5)]
        self.assertEqual(codes(good), [])
        self.assertEqual(codes(good[:5]), ["D0"])
        self.assertEqual(codes(good, tok="E"), ["D7"])
        self.assertIn("D4", codes(good[:5] + [("SL", 1)]))
        twos = [("HL", 7), ("HL", 7), ("HL", 7), ("SL", 2), ("SL", 2), ("SL", 2)]
        self.assertEqual(codes(twos), ["D3", "D5"])
        four_hl = [("HL", 6), ("HL", 4), ("HL", 3), ("HL", 2), ("SL", 3), ("SL", 3)]
        # Best three HL = 13; two SL subjects need 6.
        self.assertEqual(codes(four_hl), ["D6"])

    def test_certificate_conditions(self) -> None:
        failing, unchecked = rules.certificate_conditions([5, 4, 3], None, "D D M")
        self.assertEqual(failing, [])
        self.assertIn("Reflective Project", unchecked)
        failing, _ = rules.certificate_conditions([5, 2], "E", "U")
        self.assertEqual([c.code for c in failing], ["C1", "C2", "C6"])


class ParserValidationTests(unittest.TestCase):
    def test_rejects_non_excel(self) -> None:
        with self.assertRaises(WorkbookError):
            parse_ib_results(b"not a workbook")

    def test_reports_out_of_range_values(self) -> None:
        content = workbook_bytes(
            lambda s: results_sheet(s, [[1, "Ann", "Lee", 9, 5, 5, 5, "Eng", "B", "F", 2, 30]])
        )
        with self.assertRaises(WorkbookError) as raised:
            parse_ib_results(content)
        errors = raised.exception.errors
        self.assertTrue(any("Eng grade '9'" in e for e in errors))
        self.assertTrue(any("TOK grade 'F'" in e for e in errors))

    def test_levels_from_headings_and_fills(self) -> None:
        def build(sheet):
            results_sheet(sheet, [[1, "Ann", "Lee", 6, 5, 5, 4, "Bio", "A", "B", 3, 23]])
            sheet["E2"].fill = YELLOW
            sheet["F2"].fill = GREEN
            sheet["G2"].fill = YELLOW
            sheet["D1"] = "Eng SL"

        candidate = parse_ib_results(workbook_bytes(build)).records[0]
        self.assertEqual(
            [(s.subject, s.level, s.variant) for s in candidate.subjects],
            [("eng", "SL", None), ("fre", "SL", "ab"), ("bio", "SL", None), ("mat", "SL", "ai")],
        )
        self.assertEqual((candidate.ee_subject, candidate.ee_grade), ("Bio", "A"))

    def test_cem_requires_columns_and_valid_predictions(self) -> None:
        missing = workbook_bytes(lambda s: s.append(["Name", "Score"]))
        with self.assertRaises(WorkbookError):
            parse_cem(missing)

        def build(sheet):
            sheet.append(["StudentName", "Gender", "baseline", "Subject", "CABTIC"])
            sheet.append(["Lee, Ann", "F", 100, "IB-H-Biology", 9])
            sheet.append(["Lee, Ann", "F", 100, "Biology", 5])

        with self.assertRaises(WorkbookError) as raised:
            parse_cem(workbook_bytes(build))
        self.assertEqual(len(raised.exception.errors), 2)


class ImportApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
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
                School(code="bge", name="Braeburn Garden Estate", curricula=["ib"]),
                School(code="bs", name="Braeburn School", curricula=["igcse"]),
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

    def sign_in(self, role: str = "admin") -> None:
        email = f"{role}@example.org"
        self.db.add(
            User(
                email=email,
                name=f"{role.title()} User",
                role=role,
                is_active=True,
                failed_login_attempts=0,
                password_hash=hash_password(PASSWORD),
            )
        )
        self.db.commit()
        response = self.client.post(
            "/api/auth/login", json={"email": email, "password": PASSWORD}, headers=self.csrf()
        )
        self.assertEqual(response.status_code, 200, response.text)

    def upload(self, kind: str, content: bytes, school: str = "bge", filename: str = "data.xlsx"):
        return self.client.post(
            "/api/imports",
            data={"school": school, "kind": kind, "year": "2026", "session": "may"},
            files={"file": (filename, content, XLSX)},
            headers=self.csrf(),
        )

    def test_requires_sign_in_and_admin(self) -> None:
        self.assertEqual(self.client.get("/api/imports?school=bge").status_code, 401)
        self.assertEqual(self.client.get("/api/analysis/ib?school=bge").status_code, 401)
        self.sign_in("user")
        self.assertEqual(self.upload("cem", b"x").status_code, 403)
        self.assertEqual(self.client.get("/api/imports?school=bge").json(), [])

    def test_rejects_bad_requests(self) -> None:
        self.sign_in()
        self.assertEqual(self.upload("cem", b"x", school="nope").status_code, 404)
        self.assertEqual(self.upload("cem", b"x", school="bs").status_code, 422)
        self.assertEqual(self.upload("cem", b"x", school="all").status_code, 422)
        self.assertEqual(self.upload("other", b"x").status_code, 422)
        wrong_type = self.upload("cem", b"x", filename="data.csv")
        self.assertEqual(wrong_type.json()["detail"]["message"], "Upload an Excel workbook (.xlsx).")
        invalid = self.upload("cem", b"not excel")
        self.assertEqual(invalid.status_code, 422)
        self.assertIn("not a valid Excel workbook", invalid.json()["detail"]["message"])

    def test_analysis_is_empty_before_import(self) -> None:
        self.sign_in("user")
        body = self.client.get("/api/analysis/ib?school=bge").json()
        self.assertEqual(body["sessions"], [])
        self.assertIsNone(body["session"])
        self.assertIsNone(body["analysis"])
        self.assertEqual(self.client.get("/api/analysis/ib?school=nope").status_code, 404)

    @unittest.skipUnless(RESULTS_FILE.exists(), "sample workbooks missing")
    def test_import_analyse_replace_and_delete(self) -> None:
        self.sign_in()
        results = self.upload("ib_results", RESULTS_FILE.read_bytes(), filename="IB Results 2026.xlsx")
        self.assertEqual(results.status_code, 201, results.text)
        self.assertEqual(results.json()["summary"]["dp_candidates"], 32)
        self.assertEqual(results.json()["uploaded_by"], "Admin User")

        body = self.client.get("/api/analysis/ib?school=bge").json()
        self.assertEqual(body["session"], {"year": 2026, "session": "may"})
        self.assertIsNone(body["analysis"]["summary"]["dp"]["average_va"])

        cem = self.upload("cem", CEM_FILE.read_bytes(), filename="CEM.xlsx")
        self.assertEqual(cem.status_code, 201, cem.text)
        again = self.upload("cem", CEM_FILE.read_bytes(), filename="CEM v2.xlsx")
        self.assertEqual(again.json()["summary"]["replaced"], "CEM.xlsx")

        imports = self.client.get("/api/imports?school=bge").json()
        self.assertEqual(sorted(i["filename"] for i in imports), ["CEM v2.xlsx", "IB Results 2026.xlsx"])

        for school in ("bge", "all"):
            body = self.client.get(f"/api/analysis/ib?school={school}&year=2026&session=may").json()
            self.assertEqual(body["analysis"]["summary"]["dp"]["diploma"]["rate"], 93.8)
            self.assertIsNotNone(body["analysis"]["summary"]["dp"]["average_va"])
            self.assertEqual([s["filename"] for s in body["sources"]["cem"]], ["CEM v2.xlsx"])

        cem_id = next(i["id"] for i in imports if i["kind"] == "cem")
        self.assertEqual(self.client.delete(f"/api/imports/{cem_id}", headers=self.csrf()).status_code, 204)
        self.assertEqual(self.client.delete(f"/api/imports/{cem_id}", headers=self.csrf()).status_code, 404)
        body = self.client.get("/api/analysis/ib?school=bge").json()
        self.assertEqual(body["sources"]["cem"], [])
        self.assertEqual(body["analysis"]["matching"]["unmatched_results"], [])


if __name__ == "__main__":
    unittest.main()
