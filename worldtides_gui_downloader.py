# -*- coding: utf-8 -*-
"""
WorldTides GUI Batch Downloader
- GUI sets: start/end time (UTC), step seconds, datum, API key
- Load Excel with multiple points (columns: lat, lon, optional name)
- Download per-point tide heights via WorldTides API v3 JSON (monthly segments)
- Retries + pause + progress bar + log window
- Exports CSV per point: time_utc,tide_m

Dependencies:
  pip install requests pandas openpyxl
"""

from __future__ import annotations

import os
import re
import time
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List, Tuple

import requests
import pandas as pd
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


# -----------------------------
# Core download logic
# -----------------------------

@dataclass
class WorldTidesConfig:
    api_key: str
    datum: str = "MSL"
    step_seconds: int = 3600
    base_url: str = "https://www.worldtides.info/api/v3"
    timeout_seconds: int = 60
    pause_between_calls: float = 1.2
    max_retry: int = 3


def _dt_utc_from_str(s: str) -> datetime:
    """
    Parse user input like '2017-01-01 00:00:00' as UTC datetime.
    """
    s = s.strip()
    # Allow 'YYYY-mm-dd' or 'YYYY-mm-dd HH:MM:SS'
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        s = s + " 00:00:00"
    try:
        dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        raise ValueError("时间格式应为 'YYYY-mm-dd' 或 'YYYY-mm-dd HH:MM:SS'") from e
    return dt.replace(tzinfo=timezone.utc)


def _month_start(dt: datetime) -> datetime:
    return datetime(dt.year, dt.month, 1, tzinfo=timezone.utc)


def _next_month(dt: datetime) -> datetime:
    y, m = dt.year, dt.month
    if m == 12:
        return datetime(y + 1, 1, 1, tzinfo=timezone.utc)
    return datetime(y, m + 1, 1, tzinfo=timezone.utc)


def _posix_seconds(dt: datetime) -> int:
    return int(round(dt.timestamp()))


def _parse_worldtides_date(s: str) -> datetime:
    """
    WorldTides date examples:
      - '2017-01-01T00:00+0000'
      - '2017-01-01T00:00:00+0000'
      - '2017-01-01T00:00Z'
      - '2017-01-01T00:00:00Z'
    Normalize and parse to timezone-aware UTC datetime.
    """
    s = s.strip()
    s = re.sub(r"Z$", "+00:00", s)
    s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)

    # If no seconds, add ':00' before timezone
    m = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})([+-]\d{2}:\d{2})$", s)
    if m:
        s = f"{m.group(1)}:00{m.group(2)}"

    dt = datetime.fromisoformat(s)
    return dt.astimezone(timezone.utc)


def download_one_point(
    cfg: WorldTidesConfig,
    lat: float,
    lon: float,
    t_start_utc: datetime,
    t_end_utc: datetime,
    log_fn=None,
    progress_fn=None,
    progress_base: float = 0.0,
    progress_span: float = 1.0,
) -> pd.DataFrame:

    """
    Download one point, monthly segments. Export CSV.
    progress_fn expects 0..100. We map this point into [base, base+span].
    """
    if t_start_utc >= t_end_utc:
        raise ValueError("开始时间必须早于结束时间。")

    session = requests.Session()
    all_times: List[datetime] = []
    all_heights: List[float] = []

    tA = _month_start(t_start_utc)
    seg = 0

    # Rough estimate of months for progress
    months = 0
    tmp = tA
    while tmp < t_end_utc:
        months += 1
        tmp = _next_month(tmp)

    def _log(msg: str):
        if log_fn:
            log_fn(msg)

    def _set_prog(frac_0_1: float):
        if progress_fn:
            v = (progress_base + progress_span * frac_0_1) * 100.0
            progress_fn(v)

    while tA < t_end_utc:
        tB = min(_next_month(tA), t_end_utc)
        seg += 1

        start_unix = _posix_seconds(tA)
        length_sec = int((tB - tA).total_seconds())

        params = {
            "heights": "",  # presence flag
            "lat": f"{lat:.6f}",
            "lon": f"{lon:.6f}",
            "start": str(start_unix),
            "length": str(length_sec),
            "step": str(cfg.step_seconds),
            "datum": cfg.datum,
            "key": cfg.api_key,
        }

        _log(f"  [{seg:03d}/{months:03d}] {tA.isoformat()} → {tB.isoformat()} 请求中...")

        last_err: Optional[Exception] = None
        data = None

        for r in range(cfg.max_retry + 1):
            try:
                resp = session.get(cfg.base_url, params=params, timeout=cfg.timeout_seconds)
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as e:
                last_err = e
                if r >= cfg.max_retry:
                    raise
                wait = 2 * (r + 1)
                _log(f"     请求失败，重试 {r+1}/{cfg.max_retry}，等待 {wait}s：{e}")
                time.sleep(wait)

        heights = (data or {}).get("heights")
        if not heights:
            raise RuntimeError("响应无 heights 字段或为空（可能配额限制、参数错误或坐标无数据）。")

        for item in heights:
            dt = _parse_worldtides_date(str(item["date"]))
            h = float(item["height"])
            all_times.append(dt)
            all_heights.append(h)

        _log(f"     OK：{len(heights)} 条")
        _set_prog(seg / max(months, 1))
        time.sleep(cfg.pause_between_calls)
        tA = tB

    df = pd.DataFrame({"time_utc": all_times, "tide_m": all_heights})
    df = df.drop_duplicates(subset=["time_utc"]).sort_values("time_utc").reset_index(drop=True)

    # 用 time_utc 做索引，便于多个点位按时间对齐合并
    df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)
    df = df.set_index("time_utc")

    _set_prog(1.0)
    _log(f"  下载完成：{len(df)} 条（等待合并写出）")
    return df


# -----------------------------
# GUI
# -----------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WorldTides 批量潮位下载器（GUI）")
        self.geometry("920x620")

        self.points_df: Optional[pd.DataFrame] = None
        self.excel_path: Optional[str] = None
        self.out_dir: str = os.path.abspath(os.getcwd())

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 8, "pady": 6}

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=False, **pad)

        # API Key
        ttk.Label(frm, text="API Key").grid(row=0, column=0, sticky="w", **pad)
        self.api_key_var = tk.StringVar(value="94b0be98-af8d-42d6-bbbb-89ae034cb56e")
        api_entry = ttk.Entry(frm, textvariable=self.api_key_var, width=60)
        api_entry.grid(row=0, column=1, sticky="w", **pad)
        api_entry.icursor("end")  # 光标到末尾
        ttk.Entry(frm, textvariable=self.api_key_var, width=60).grid(row=0, column=1, sticky="w", **pad)

        # Datum
        ttk.Label(frm, text="Datum").grid(row=0, column=2, sticky="w", **pad)
        self.datum_var = tk.StringVar(value="MSL")
        ttk.Combobox(frm, textvariable=self.datum_var, values=["MSL", "LAT", "HAT"], width=10, state="readonly")\
            .grid(row=0, column=3, sticky="w", **pad)

        # Time range
        ttk.Label(frm, text="开始时间(UTC)").grid(row=1, column=0, sticky="w", **pad)
        self.t_start_var = tk.StringVar(value="2017-01-01 00:00:00")
        ttk.Entry(frm, textvariable=self.t_start_var, width=22).grid(row=1, column=1, sticky="w", **pad)

        ttk.Label(frm, text="结束时间(UTC)").grid(row=1, column=2, sticky="w", **pad)
        self.t_end_var = tk.StringVar(value="2019-01-01 00:00:00")
        ttk.Entry(frm, textvariable=self.t_end_var, width=22).grid(row=1, column=3, sticky="w", **pad)

        # Step
        ttk.Label(frm, text="时间分辨率(step)").grid(row=2, column=0, sticky="w", **pad)
        self.step_var = tk.StringVar(value="3600 (1小时)")
        step_choices = [
            "300 (5分钟)", "600 (10分钟)", "900 (15分钟)", "1800 (30分钟)",
            "3600 (1小时)", "7200 (2小时)", "10800 (3小时)"
        ]
        ttk.Combobox(frm, textvariable=self.step_var, values=step_choices, width=18, state="readonly")\
            .grid(row=2, column=1, sticky="w", **pad)

        ttk.Label(frm, text="请求间隔(s)").grid(row=2, column=2, sticky="w", **pad)
        self.pause_var = tk.StringVar(value="1.2")
        ttk.Entry(frm, textvariable=self.pause_var, width=10).grid(row=2, column=3, sticky="w", **pad)

        # Excel + output
        ttk.Button(frm, text="载入点位Excel...", command=self.load_excel).grid(row=3, column=0, sticky="w", **pad)
        self.excel_label = ttk.Label(frm, text="未选择文件")
        self.excel_label.grid(row=3, column=1, columnspan=3, sticky="w", **pad)

        ttk.Button(frm, text="选择输出目录...", command=self.choose_out_dir).grid(row=4, column=0, sticky="w", **pad)
        self.out_label = ttk.Label(frm, text=self.out_dir)
        self.out_label.grid(row=4, column=1, columnspan=3, sticky="w", **pad)

        # Buttons
        self.start_btn = ttk.Button(frm, text="开始下载", command=self.start_download)
        self.start_btn.grid(row=5, column=0, sticky="w", **pad)

        self.stop_flag = threading.Event()
        self.stop_btn = ttk.Button(frm, text="停止（当前月后退出）", command=self.stop_download, state="disabled")
        self.stop_btn.grid(row=5, column=1, sticky="w", **pad)

        # Progress
        self.progress = ttk.Progressbar(self, orient="horizontal", length=860, mode="determinate")
        self.progress.pack(padx=12, pady=8)
        self.progress["value"] = 0

        # Points preview
        self.points_text = tk.Text(self, height=10, wrap="none")
        self.points_text.pack(fill="x", padx=12, pady=6)
        self.points_text.insert("end", "点位预览：\n（载入Excel后显示前几行）\n")

        # Log window
        self.log_text = tk.Text(self, height=16, wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=12, pady=8)
        self._log("准备就绪。请填写 API Key，载入点位Excel，设置时间与分辨率，然后开始下载。")

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] {msg}\n")
        self.log_text.see("end")
        self.update_idletasks()

    def set_progress(self, v: float):
        # v: 0..100
        self.progress["value"] = max(0.0, min(100.0, v))
        self.update_idletasks()

    def load_excel(self):
        path = filedialog.askopenfilename(
            title="选择点位Excel",
            filetypes=[("Excel files", "*.xlsx *.xls")]
        )
        if not path:
            return

        try:
            df = pd.read_excel(path)
        except Exception as e:
            messagebox.showerror("读取失败", f"无法读取Excel：{e}")
            return

        # Normalize columns
        cols = {c.lower().strip(): c for c in df.columns}
        if "lat" not in cols or "lon" not in cols:
            messagebox.showerror("格式错误", "Excel必须包含列：lat, lon（大小写不敏感）。可选：name")
            return

        lat_col = cols["lat"]
        lon_col = cols["lon"]
        name_col = cols.get("name")

        df2 = pd.DataFrame()
        df2["lat"] = pd.to_numeric(df[lat_col], errors="coerce")
        df2["lon"] = pd.to_numeric(df[lon_col], errors="coerce")
        if name_col:
            df2["name"] = df[name_col].astype(str)
        else:
            df2["name"] = [f"Point{i+1}" for i in range(len(df2))]

        df2 = df2.dropna(subset=["lat", "lon"]).reset_index(drop=True)
        if df2.empty:
            messagebox.showerror("无有效点位", "Excel里没有有效 lat/lon。")
            return

        self.points_df = df2
        self.excel_path = path
        self.excel_label.config(text=os.path.basename(path))

        # Preview
        self.points_text.delete("1.0", "end")
        self.points_text.insert("end", "点位预览（前10行）：\n")
        self.points_text.insert("end", df2.head(10).to_string(index=False))
        self.points_text.insert("end", "\n")

        self._log(f"已载入点位：{len(df2)} 个。")

    def choose_out_dir(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if not d:
            return
        self.out_dir = d
        self.out_label.config(text=self.out_dir)
        self._log(f"输出目录：{self.out_dir}")

    def stop_download(self):
        self.stop_flag.set()
        self._log("已请求停止：将在当前月分段完成后退出。")

    def start_download(self):
        if not self.api_key_var.get().strip():
            messagebox.showwarning("缺少API Key", "请先填写 API Key。")
            return
        if self.points_df is None or self.points_df.empty:
            messagebox.showwarning("缺少点位", "请先载入点位Excel。")
            return

        try:
            t_start = _dt_utc_from_str(self.t_start_var.get())
            t_end = _dt_utc_from_str(self.t_end_var.get())
        except Exception as e:
            messagebox.showerror("时间格式错误", str(e))
            return

        if t_start >= t_end:
            messagebox.showerror("时间范围错误", "开始时间必须早于结束时间。")
            return

        # Step parse
        try:
            step_seconds = int(self.step_var.get().split()[0])
        except Exception:
            messagebox.showerror("step错误", "无法解析时间分辨率(step)。")
            return

        try:
            pause = float(self.pause_var.get().strip())
        except Exception:
            messagebox.showerror("参数错误", "请求间隔(s)必须是数字。")
            return

        cfg = WorldTidesConfig(
            api_key=self.api_key_var.get().strip(),
            datum=self.datum_var.get().strip(),
            step_seconds=step_seconds,
            pause_between_calls=max(0.0, pause),
        )

        self.stop_flag.clear()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.set_progress(0)

        # Run in background thread
        th = threading.Thread(
            target=self._download_worker,
            args=(cfg, t_start, t_end),
            daemon=True
        )
        th.start()

    def _download_worker(self, cfg: WorldTidesConfig, t_start: datetime, t_end: datetime):
        try:
            pts = self.points_df.copy()
            n = len(pts)
            series_list = []  # 存每个点位的 Series（列）
            col_names = []  # 记录列名，避免重名

            self._log(f"开始下载：点位 {n} 个；时间 {t_start.isoformat()} → {t_end.isoformat()}；step={cfg.step_seconds}s；datum={cfg.datum}")

            for i, row in pts.iterrows():
                if self.stop_flag.is_set():
                    self._log("检测到停止请求，退出下载。")
                    break

                name = str(row["name"]).strip() if "name" in row else f"Point{i+1}"
                lat = float(row["lat"])
                lon = float(row["lon"])

                base_name = name
                k = 1
                while name in col_names:
                    k += 1
                    name = f"{base_name}_{k}"
                col_names.append(name)

                self._log(f"点位 {i + 1}/{n}：{name} (lat={lat}, lon={lon})")
                base = i / max(n, 1)
                span = 1 / max(n, 1)

                df_point = download_one_point(
                    cfg=cfg,
                    lat=lat,
                    lon=lon,
                    t_start_utc=t_start,
                    t_end_utc=t_end,
                    log_fn=self._log,
                    progress_fn=self.set_progress,
                    progress_base=base,
                    progress_span=span,
                )

                # df_point: index=time_utc, column=tide_m
                s = df_point["tide_m"].rename(name)
                series_list.append(s)

                # 合并所有点位为一个宽表：time_utc + 各点位列
                if series_list:
                    df_all = pd.concat(series_list, axis=1, join="outer").sort_index()

                    df_out = df_all.reset_index()
                    # time_utc 输出为字符串
                    df_out["time_utc"] = pd.to_datetime(df_out["time_utc"], utc=True).dt.strftime("%Y-%m-%d %H:%M:%S")

                    out_csv = os.path.join(
                        self.out_dir,
                        f"WorldTides_MULTI_{t_start:%Y%m%d}_{t_end:%Y%m%d}_{cfg.step_seconds}s.csv"
                    )
                    df_out.to_csv(out_csv, index=False, encoding="utf-8-sig")
                    self._log(f"合并写出完成：{out_csv}（行={len(df_out)}，点位列={df_out.shape[1] - 1}）")
                else:
                    self._log("没有可写出的数据（可能全部失败或被停止）。")

            self._log("全部任务结束。")
        except Exception as e:
            self._log(f"发生错误：{e}")
            messagebox.showerror("下载失败", str(e))
        finally:
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            if self.stop_flag.is_set():
                self._log("状态：已停止。")
            else:
                self.set_progress(100)
                self._log("状态：完成。")


if __name__ == "__main__":
    app = App()
    app.mainloop()