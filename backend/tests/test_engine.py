import copy
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
import engine


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.p = engine.example("poste")

    def test_embedded_spt_overrides_external_path(self):
        self.p["sondagem"]["arquivo"] = "/etc/passwd"
        self.assertIsNone(engine.prepare(self.p)["sondagem"]["arquivo"])

    def test_external_path_alone_is_rejected(self):
        self.p["sondagem"]["sondagens"] = None
        self.p["sondagem"]["arquivo"] = "/etc/passwd"
        with self.assertRaisesRegex(ValueError, "Importe"):
            engine.prepare(self.p)

    def test_unimplemented_inputs_are_not_silently_accepted(self):
        for section, key, value in [("sondagem", "submodo", "2.3_dois_paralelos"), ("geometria", "D_base", 3)]:
            with self.subTest(key=key):
                p = copy.deepcopy(self.p)
                p[section][key] = value
                with self.assertRaises(ValueError):
                    engine.prepare(p)
        self.p["acoes"][0]["tipo"] = "excepcional"
        with self.assertRaisesRegex(ValueError, "excepcionais"):
            engine.prepare(self.p)

    def test_bounds_prevent_infinite_or_excessive_search(self):
        for section, key, value in [("dimensionamento", "L_passo", 0), ("dimensionamento", "L_passo", -.5),
                                     ("camisa", "altura", 0), ("analise", "n_fatias", 0),
                                     ("materiais", "fck", float("nan")), ("materiais", "fck", True),
                                     ("geometria", "L", "2"), ("geometria", "L", float("inf"))]:
            with self.subTest(key=key, value=value):
                p = copy.deepcopy(self.p)
                p[section][key] = value
                with self.assertRaises(ValueError):
                    engine.prepare(p)

    def test_stale_derived_nspt_is_recomputed(self):
        f = self.p["sondagem"]["sondagens"]
        f["SP-A"]["leituras"][0].update(nspt_real=7, nspt_calculo=50)
        self.assertEqual(engine.import_sondagem(f)["SP-A"]["leituras"][0]["nspt_calculo"], 7)

    def test_empty_or_duplicate_spt_rejected(self):
        for hole in [dict(cotaTopo_m=0, leituras=[]), dict(cotaTopo_m=0, leituras=[dict(profundidade_m=1, nspt=4, solo="Areia")] * 2)]:
            with self.assertRaises(ValueError):
                engine.import_sondagem({"SP": hole})

    def test_duplicate_action_names_rejected(self):
        self.p["acoes"][1]["nome"] = self.p["acoes"][0]["nome"]
        with self.assertRaisesRegex(ValueError, "únicos"):
            engine.prepare(self.p)

    def test_unknown_spt_version_rejected(self):
        with self.assertRaisesRegex(ValueError, "GEOSPT"):
            engine.import_sondagem({"_schema": "geospt-obra", "_schemaVersao": "99.0"})

    def test_invalid_manual_soil_stiffness_rejected(self):
        self.p["solo"]["edicoes"] = [{"cota_m": 38, "kv": -10}]
        with self.assertRaises(ValueError):
            engine.prepare(self.p)


class NumericalRegressionTests(unittest.TestCase):
    def test_supplied_reference_suite(self):
        run = subprocess.run([sys.executable, str(engine.LEGACY / "tubulao_testes.py")], capture_output=True, text=True, timeout=90)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("TODOS OS TESTES PASSARAM", run.stdout)

    def test_three_original_examples(self):
        expected = json.loads((ROOT / "backend/tests/reference-results.json").read_text())
        for name, fixture in expected.items():
            with self.subTest(example=name):
                adapted = engine.calculate(engine.example(name))
                r = adapted["result"]
                self.assertEqual(r["ok"], fixture["ok"])
                self.assertAlmostEqual(r["p"]["geometria"]["D"], fixture["D"], places=8)
                self.assertAlmostEqual(r["p"]["geometria"]["L"], fixture["L"], places=8)
                self.assertEqual(len(r["verificacoes"]), fixture["checks"])
                self.assertAlmostEqual(r["governante"]["aproveitamento"], fixture["utilization"], places=7)
                self.assertEqual(r["estrutura"]["armadura"] and r["estrutura"]["armadura"]["n"], fixture["bars"])
                self.assertIn("TubStruct", adapted["report"])
                self.assertIn("<svg", adapted["drawings"]["elevacao"])
                json.dumps(adapted, allow_nan=False)

    def test_failed_design_is_not_reported_as_passed(self):
        p = engine.example("poste")
        p["acoes"][1]["My"] = 10000
        r = engine.calculate(p)["result"]
        self.assertFalse(r["ok"])
        self.assertTrue(any(not c["ok"] for c in r["verificacoes"]) or any(a[0] == "erro" for a in r["alertas"]))

    def test_worker_protocol_and_error(self):
        for request, ok in [({"action": "health"}, True), ({"action": "calculate", "parameters": {}}, False)]:
            run = subprocess.run([sys.executable, str(ROOT / "backend/worker.py")], input=json.dumps(request), text=True, capture_output=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["ok"], ok)

    def test_preserved_source_hashes(self):
        manifest = json.loads((ROOT / "docs/legacy-manifest.json").read_text())
        for filename, digest in manifest["files_sha256"].items():
            actual = hashlib.sha256((engine.LEGACY / filename).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            self.assertEqual(actual, digest, filename)


if __name__ == "__main__":
    unittest.main()
