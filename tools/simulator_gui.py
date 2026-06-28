"""街道バランスシミュレーター GUI版。

PowerShellで以下を実行:
  python tools\simulator_gui.py

または tools\run_land_simulator_gui.bat をダブルクリック。
"""
from __future__ import annotations

import csv
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, StringVar, Text, Tk, ttk, messagebox

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
REPORT_DIR = TOOLS / "sim_reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import simulate_land as sim  # noqa: E402

AREA_OPTIONS = {
    "平原": 1,
    "森": 2,
    "山": 3,
}

RUN_OPTIONS = ["1000", "10000", "100000", "1000000"]


def counter_to_lines(counter, name_map=None, limit=999):
    if not counter:
        return ["  なし"]
    lines = []
    for key, val in counter.most_common(limit):
        label = name_map.get(key, key) if name_map else key
        lines.append(f"  {label}: {val:,}")
    return lines


def build_report(result: dict) -> str:
    import land_config as L  # local import so GUI starts even if config is edited
    import voyage_config as V

    item_names = {iid: f"{d.get('emoji', '')} {d.get('name', iid)}" for iid, d in L.LAND_ITEMS.items()}
    item_names.update({f"food:{fid}": f"{f.get('emoji', '')} {f.get('name', fid)}" for fid, f in V.FOODS.items()})

    runs = int(result["runs"])
    total_coin = int(result["total_coin"])
    total_xp = int(result["total_xp"])
    events = result["events"]
    sub = result["sub"]
    items = result["items"]
    equips = result["equips"]

    lines = []
    lines.append(f"====== 街道シミュレーション: {result['area_name']} {runs:,}回 ======")
    lines.append("")
    lines.append(f"開始Lv: {result['start_level']}  →  最終Lv: {result['final_level']}")
    lines.append(f"現在XP: {result['xp_pool']:,}/{sim.xp_to_next(result['final_level']):,}")
    lines.append(f"総XP: {total_xp:,} / 1探索平均: {total_xp / max(1, runs):,.2f}")
    lines.append(f"総コイン: {total_coin:,} / 1探索平均: {total_coin / max(1, runs):,.2f}")
    lines.append(f"レベルアップ回数: {result['levelups']:,}")
    lines.append("")
    lines.append("[イベント]")
    lines.extend(counter_to_lines(events))
    lines.append("")
    lines.append("[イベント内サブ結果]")
    lines.extend(counter_to_lines(sub))
    lines.append("")
    lines.append("[消耗品]")
    lines.extend(counter_to_lines(items, item_names))
    lines.append("")
    lines.append("[装備ドロップ]")
    lines.extend(counter_to_lines(equips))
    lines.append("")
    lines.append("[バランス確認メモ]")
    lines.append("  ※このPhase1版は『遭遇した敵は勝利した前提』で、報酬/XP/ドロップ期待値を見るツールです。")
    lines.append("  ※死亡率・実戦闘勝率・回復アイテム消費の精密計算は次フェーズで追加予定です。")
    return "\n".join(lines)


def save_text_report(report: str, area_label: str, runs: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"land_gui_{area_label}_{runs}_{ts}.txt"
    path.write_text(report, encoding="utf-8")
    return path


def save_csv_summary(result: dict, area_label: str, runs: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"land_gui_{area_label}_{runs}_{ts}.csv"
    rows = [
        ["area", result["area_name"]],
        ["runs", result["runs"]],
        ["start_level", result["start_level"]],
        ["final_level", result["final_level"]],
        ["total_xp", result["total_xp"]],
        ["total_coin", result["total_coin"]],
        ["levelups", result["levelups"]],
    ]
    rows.append([])
    rows.append(["events"])
    for k, v in result["events"].most_common():
        rows.append([k, v])
    rows.append([])
    rows.append(["sub_outcomes"])
    for k, v in result["sub"].most_common():
        rows.append([k, v])
    rows.append([])
    rows.append(["items"])
    for k, v in result["items"].most_common():
        rows.append([k, v])
    rows.append([])
    rows.append(["equips"])
    for k, v in result["equips"].most_common():
        rows.append([k, v])
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows(rows)
    return path


class LandSimulatorGUI:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title("Discord RPG Simulator - 街道")
        self.root.geometry("920x720")
        self.root.minsize(820, 600)

        self.area_var = StringVar(value="平原")
        self.runs_var = StringVar(value="1000")
        self.level_var = StringVar(value="1")
        self.seed_var = StringVar(value="1")
        self.status_var = StringVar(value="待機中")
        self.last_result = None
        self.last_report = ""

        self._build_widgets()

    def _build_widgets(self) -> None:
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="エリア").pack(side=LEFT, padx=(0, 6))
        area_box = ttk.Combobox(top, textvariable=self.area_var, values=list(AREA_OPTIONS.keys()), state="readonly", width=10)
        area_box.pack(side=LEFT, padx=(0, 14))

        ttk.Label(top, text="探索回数").pack(side=LEFT, padx=(0, 6))
        runs_box = ttk.Combobox(top, textvariable=self.runs_var, values=RUN_OPTIONS, width=12)
        runs_box.pack(side=LEFT, padx=(0, 14))

        ttk.Label(top, text="開始Lv").pack(side=LEFT, padx=(0, 6))
        ttk.Entry(top, textvariable=self.level_var, width=8).pack(side=LEFT, padx=(0, 14))

        ttk.Label(top, text="Seed").pack(side=LEFT, padx=(0, 6))
        ttk.Entry(top, textvariable=self.seed_var, width=8).pack(side=LEFT, padx=(0, 14))

        self.run_btn = ttk.Button(top, text="シミュ実行", command=self.run_simulation)
        self.run_btn.pack(side=LEFT, padx=(0, 8))
        ttk.Button(top, text="レポート保存", command=self.save_current_report).pack(side=LEFT)

        info = ttk.Frame(self.root, padding=(10, 0, 10, 8))
        info.pack(fill="x")
        ttk.Label(info, textvariable=self.status_var).pack(side=LEFT)
        ttk.Label(info, text="  ※Phase1: 敵は倒した前提で報酬期待値を見る版").pack(side=RIGHT)

        body = ttk.Frame(self.root, padding=10)
        body.pack(fill=BOTH, expand=True)
        self.output = Text(body, wrap="word", font=("Consolas", 11))
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.output.yview)
        self.output.configure(yscrollcommand=scroll.set)
        self.output.pack(side=LEFT, fill=BOTH, expand=True)
        scroll.pack(side=RIGHT, fill="y")

        self.output.insert(END, "エリア・探索回数を選んで『シミュ実行』を押してね。\n\n")
        self.output.insert(END, "例：平原 1000回 / 森 10000回 / 山 100000回\n")

    def run_simulation(self) -> None:
        try:
            area_label = self.area_var.get()
            area = AREA_OPTIONS[area_label]
            runs = int(self.runs_var.get().replace(",", ""))
            start_level = int(self.level_var.get())
            seed_text = self.seed_var.get().strip()
            seed = int(seed_text) if seed_text else None
            if runs <= 0 or runs > 5_000_000:
                raise ValueError("探索回数は1〜5,000,000で指定してね")
            if start_level <= 0:
                raise ValueError("開始Lvは1以上で指定してね")
        except Exception as e:
            messagebox.showerror("入力エラー", str(e))
            return

        self.run_btn.configure(state="disabled")
        self.status_var.set("実行中… 少し待ってね")
        self.output.delete("1.0", END)
        self.output.insert(END, "シミュレーション中…\n")

        def worker():
            try:
                result = sim.simulate(area=area, runs=runs, start_level=start_level, seed=seed)
                report = build_report(result)
                self.last_result = result
                self.last_report = report
                self.root.after(0, lambda: self._finish_success(report))
            except Exception:
                err = traceback.format_exc()
                self.root.after(0, lambda: self._finish_error(err))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_success(self, report: str) -> None:
        self.output.delete("1.0", END)
        self.output.insert(END, report)
        self.status_var.set("完了")
        self.run_btn.configure(state="normal")

    def _finish_error(self, err: str) -> None:
        self.output.delete("1.0", END)
        self.output.insert(END, err)
        self.status_var.set("エラー")
        self.run_btn.configure(state="normal")
        messagebox.showerror("エラー", "シミュレーション中にエラーが出たよ。ログを確認してね。")

    def save_current_report(self) -> None:
        if not self.last_report or not self.last_result:
            messagebox.showinfo("保存なし", "先にシミュレーションを実行してね。")
            return
        area_label = self.area_var.get()
        runs = self.runs_var.get().replace(",", "")
        txt = save_text_report(self.last_report, area_label, runs)
        csv_path = save_csv_summary(self.last_result, area_label, runs)
        messagebox.showinfo("保存完了", f"保存したよ:\n{txt}\n{csv_path}")

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    LandSimulatorGUI().run()
