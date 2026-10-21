"""extensions.py の変異を tests/p2 で検査する。使い方: python3 -B scripts/research/p2/mutrun_p2.py [ID ...]（環境変数 P2_REPO＝作業ツリー、P2_SCRATCH＝作業場所。既定は、このリポジトリと一時ディレクトリ）"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from mutants_extensions import M
REPO = Path(os.environ.get("P2_REPO") or Path(__file__).resolve().parents[3]).resolve()
S = Path(os.environ.get("P2_SCRATCH") or tempfile.mkdtemp(prefix="p2-mutation-"))
(S / "logs").mkdir(parents=True, exist_ok=True)
only = sys.argv[1:]
out = []
for (i, f, old, new, po) in M:
    if f != "extensions.py" or (only and i not in only): continue
    d = S / "mutp2" / i
    if d.exists(): shutil.rmtree(d)
    d.mkdir(parents=True)
    for sub in ("src", "tests", "examples", "scripts", "extensions"):
        shutil.copytree(REPO / sub, d / sub, ignore=shutil.ignore_patterns("__pycache__"))
    (d / "docs").mkdir()
    shutil.copytree(REPO / "docs/research", d / "docs/research")
    p = d / "src/med_dsl" / f
    src = p.read_text(); assert src.count(old) == 1, (i, src.count(old))
    p.write_text(src.replace(old, new))
    env = dict(os.environ, PYTHONPATH=str(d / "src"), PYTHONDONTWRITEBYTECODE="1", GIT_DIR=str(REPO / ".git"))
    # P2_MUTATION_TESTS（空白区切りのモジュール名）で、実行するテストを絞れる。絞った場合の「検出」は十分、「未検出」は全体での確認が要る
    selected = os.environ.get("P2_MUTATION_TESTS", "").split()
    command = [sys.executable, "-B", "-m", "unittest", *selected] if selected else [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests/p2"]
    if selected:
        env["PYTHONPATH"] = os.pathsep.join([str(d / "src"), str(d / "tests/p2"), str(d / "scripts/research"), str(d / "scripts/research/p2"), str(d)])
    t = subprocess.run(command, cwd=d, capture_output=True, text=True, env=env, timeout=900)
    failed = sum(1 for l in t.stderr.splitlines() if l.startswith(("FAIL:", "ERROR:")))
    out.append({"id": i, "failed": failed, "detected": failed > 0})
    print(i, "失敗=%d" % failed, "検出" if failed else "未検出", flush=True)
    shutil.rmtree(d)
(S / "logs" / "mutation-p2-partial.json" if only else S / "logs" / "mutation-p2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
