from app.__main__ import main


def test_main_inicializa_e_persiste(monkeypatch, tmp_path):
    monkeypatch.setenv("PRINTNEST_HOME", str(tmp_path))
    assert main([]) == 0
    assert (tmp_path / "config.json").exists()
    assert (tmp_path / "logs" / "printnest.log").exists()
