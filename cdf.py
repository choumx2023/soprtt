import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from pathlib import Path

# =========================================================
# 路径
# =========================================================
csv_path = "/Users/choumingxi/Desktop/soprtt/mlt_full_series.csv"
out_dir = "/Users/choumingxi/Desktop/thuthesis-master/figures"

stats_csv = f"{out_dir}/rtt_accuracy_by_type.csv"
fig_bar = f"{out_dir}/rtt_accuracy_by_type_bar.png"
fig_box = f"{out_dir}/rtt_error_boxplot.png"

# =========================================================
# 中文字体（尽量贴近学位论文）
# =========================================================
candidate_fonts = [
    "Songti SC",
    "STSong",
    "PingFang SC",
    "Heiti SC",
    "Arial Unicode MS",
]

available_fonts = {f.name for f in fm.fontManager.ttflist}
chosen_font = None
for f in candidate_fonts:
    if f in available_fonts:
        chosen_font = f
        break

if chosen_font:
    plt.rcParams["font.family"] = chosen_font
plt.rcParams["axes.unicode_minus"] = False

print("当前使用字体:", chosen_font)

# =========================================================
# 参数
# =========================================================
TARGET_ACK_SENDER = "183.172.73.211"
TYPES = ["syn", "b2b", "data"]

# 误差阈值：20ms
ERR_THRESHOLD = 0.020   # seconds

# 跳变阶段两侧剔除时间：例如 5 秒
TRANSITION_GUARD = 5    # seconds

# 实验阶段
# 正常阶段理论值 = 0s
# 注入阶段理论值 = 0.4s
PHASES = [
    ("正常阶段1",       "2026-03-01 18:00:31", "2026-03-01 18:01:31", 0.0, "normal"),
    ("注入时延阶段1",   "2026-03-01 18:01:31", "2026-03-01 18:02:31", 0.4, "delay"),
    ("正常阶段2",       "2026-03-01 18:02:31", "2026-03-01 18:04:31", 0.0, "normal"),
    ("断网阶段",        "2026-03-01 18:04:31", "2026-03-01 18:05:02", None, "ignore"),
    ("恢复后正常阶段",   "2026-03-01 18:05:02", "2026-03-01 18:07:02", 0.0, "normal"),
    ("注入时延阶段2",   "2026-03-01 18:07:02", "2026-03-01 18:08:02", 0.4, "delay"),
    ("最终正常阶段",     "2026-03-01 18:08:02", "2026-03-01 18:09:02", 0.0, "normal"),
]

# =========================================================
# 读取数据
# =========================================================
df = pd.read_csv(csv_path)

df["time_utc8"] = pd.to_datetime(df["time_utc8"], errors="coerce")
df["mlt"] = pd.to_numeric(df["mlt"], errors="coerce")
df["type"] = df["type"].astype(str).str.lower().str.strip()
df["ack_sender"] = df["ack_sender"].astype(str).str.strip()

df = df.dropna(subset=["time_utc8", "mlt", "type", "ack_sender"]).copy()
df = df[df["ack_sender"] == TARGET_ACK_SENDER].copy()
df = df[df["type"].isin(TYPES)].copy()

print("过滤后总样本数:", len(df))
print(df["type"].value_counts())

# =========================================================
# 给样本打阶段标签，并剔除跳变区间
# =========================================================
phase_rows = []
for name, start, end, target, group in PHASES:
    phase_rows.append({
        "phase_name": name,
        "start": pd.Timestamp(start),
        "end": pd.Timestamp(end),
        "target": target,
        "group": group,
    })
phase_df = pd.DataFrame(phase_rows)

df["phase_name"] = None
df["target_rtt"] = np.nan
df["phase_group"] = None

for _, row in phase_df.iterrows():
    start = row["start"]
    end = row["end"]

    # 跳变边界两侧剔除 guard 秒
    effective_start = start + pd.Timedelta(seconds=TRANSITION_GUARD)
    effective_end = end - pd.Timedelta(seconds=TRANSITION_GUARD)

    if effective_start >= effective_end:
        continue

    mask = (df["time_utc8"] >= effective_start) & (df["time_utc8"] < effective_end)
    df.loc[mask, "phase_name"] = row["phase_name"]
    df.loc[mask, "phase_group"] = row["group"]
    if row["target"] is not None:
        df.loc[mask, "target_rtt"] = row["target"]

# 只保留 normal / delay，忽略断网等
df_eval = df[df["phase_group"].isin(["normal", "delay"])].copy()

print("\n剔除跳变阶段后可用于评估的样本数:", len(df_eval))
print(df_eval["phase_group"].value_counts())

# =========================================================
# 计算误差
# =========================================================
df_eval["abs_error"] = (df_eval["mlt"] - df_eval["target_rtt"]).abs()
df_eval["is_correct"] = df_eval["abs_error"] <= ERR_THRESHOLD

# =========================================================
# 统计函数
# =========================================================
def q95(x):
    return x.quantile(0.95) if len(x) > 0 else np.nan

summary = (
    df_eval
    .groupby(["type", "phase_group"])
    .agg(
        样本数=("mlt", "count"),
        平均RTT=("mlt", "mean"),
        中位RTT=("mlt", "median"),
        理论RTT=("target_rtt", "median"),
        MAE=("abs_error", "mean"),
        中位绝对误差=("abs_error", "median"),
        分位95绝对误差=("abs_error", q95),
        正确样本数=("is_correct", "sum"),
        正确率=("is_correct", "mean"),
    )
    .reset_index()
)

summary["正确率"] = summary["正确率"] * 100
summary["平均RTT"] = summary["平均RTT"].round(6)
summary["中位RTT"] = summary["中位RTT"].round(6)
summary["理论RTT"] = summary["理论RTT"].round(6)
summary["MAE"] = summary["MAE"].round(6)
summary["中位绝对误差"] = summary["中位绝对误差"].round(6)
summary["分位95绝对误差"] = summary["分位95绝对误差"].round(6)
summary["正确率"] = summary["正确率"].round(2)

print("\n=== 按类型和阶段统计 ===")
print(summary.to_string(index=False))

# 汇总 normal+delay 两个阶段
overall = (
    df_eval
    .groupby("type")
    .agg(
        样本数=("mlt", "count"),
        MAE=("abs_error", "mean"),
        中位绝对误差=("abs_error", "median"),
        分位95绝对误差=("abs_error", q95),
        正确样本数=("is_correct", "sum"),
        正确率=("is_correct", "mean"),
    )
    .reset_index()
)

overall["正确率"] = (overall["正确率"] * 100).round(2)
overall["MAE"] = overall["MAE"].round(6)
overall["中位绝对误差"] = overall["中位绝对误差"].round(6)
overall["分位95绝对误差"] = overall["分位95绝对误差"].round(6)

print("\n=== 总体统计（normal + delay）===")
print(overall.to_string(index=False))

Path(out_dir).mkdir(parents=True, exist_ok=True)
with pd.ExcelWriter(stats_csv.replace(".csv", ".xlsx")) as writer:
    summary.to_excel(writer, sheet_name="by_phase", index=False)
    overall.to_excel(writer, sheet_name="overall", index=False)

summary.to_csv(stats_csv, index=False, encoding="utf-8-sig")
print(f"\n统计结果已保存到: {stats_csv}")

# =========================================================
# 图1：正确率柱状图（按时间条件分组）
# =========================================================
plot_df = summary.copy()

# 固定顺序：先 normal，再 delay；每组内部 syn、b2b、data 并排
phase_order = ["normal", "delay"]
type_order = ["syn", "b2b", "data"]

plot_df["phase_group"] = pd.Categorical(plot_df["phase_group"], categories=phase_order, ordered=True)
plot_df["type"] = pd.Categorical(plot_df["type"], categories=type_order, ordered=True)
plot_df = plot_df.sort_values(["phase_group", "type"]).copy()

# 构造位置：每个大组一个时间条件，组内三个类型并排
base_positions = np.array([0, 1])
bar_width = 0.22
offsets = {
    "syn": -bar_width,
    "b2b": 0.0,
    "data": bar_width,
}

# 同一时间条件下使用同一色系，方便比较
color_map = {
    ("normal", "syn"): "#4C72B0",
    ("normal", "b2b"): "#6C8EBF",
    ("normal", "data"): "#8CA7CF",
    ("delay", "syn"): "#DD8452",
    ("delay", "b2b"): "#E49A73",
    ("delay", "data"): "#EBB194",
}

label_map = {
    ("normal", "syn"): "正常-syn",
    ("normal", "b2b"): "正常-b2b",
    ("normal", "data"): "正常-data",
    ("delay", "syn"): "注入时延-syn",
    ("delay", "b2b"): "注入时延-b2b",
    ("delay", "data"): "注入时延-data",
}

plt.figure(figsize=(10, 5))

for phase_idx, phase in enumerate(phase_order):
    base_x = base_positions[phase_idx]
    for t in type_order:
        sub = plot_df[(plot_df["phase_group"] == phase) & (plot_df["type"] == t)]
        if len(sub) == 0:
            continue
        y = float(sub.iloc[0]["正确率"])
        x = base_x + offsets[t]
        plt.bar(x, y, width=bar_width * 0.9, color=color_map[(phase, t)], label=label_map[(phase, t)])
        plt.text(x, y + 0.1, f"{y:.2f}", ha="center", va="bottom", fontsize=9)

plt.ylabel("误差不超过20ms的比例（%）")
plt.xlabel("时间条件")
plt.title("不同样本类型对理论链路时延的拟合准确率")
plt.xticks(base_positions, ["正常", "注入时延"])
plt.ylim(90, 100)
plt.legend(ncol=2)
plt.tight_layout()
plt.savefig(fig_bar, dpi=300, bbox_inches="tight")
plt.show()

print(f"柱状图已保存到: {fig_bar}")

# =========================================================
# 图2：绝对误差箱线图（按时间条件分组）
# =========================================================
phase_order = ["normal", "delay"]
type_order = ["syn", "b2b", "data"]

box_data = []
positions = []
labels = []
colors = []

base_positions = np.array([0, 1])
box_width = 0.22
offsets = {
    "syn": -box_width,
    "b2b": 0.0,
    "data": box_width,
}

color_map = {
    ("normal", "syn"): "#4C72B0",
    ("normal", "b2b"): "#6C8EBF",
    ("normal", "data"): "#8CA7CF",
    ("delay", "syn"): "#DD8452",
    ("delay", "b2b"): "#E49A73",
    ("delay", "data"): "#EBB194",
}

for phase_idx, phase in enumerate(phase_order):
    base_x = base_positions[phase_idx]
    for t in type_order:
        sub = df_eval[(df_eval["type"] == t) & (df_eval["phase_group"] == phase)]["abs_error"]
        if len(sub) > 0:
            box_data.append(sub.values)
            positions.append(base_x + offsets[t])
            labels.append(f"{phase}-{t}")
            colors.append(color_map[(phase, t)])

plt.figure(figsize=(10, 5))
bp = plt.boxplot(box_data, positions=positions, widths=box_width * 0.8, showfliers=False, patch_artist=True)

for patch, color in zip(bp["boxes"], colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.8)

plt.ylabel("相对理论值的绝对误差（秒）")
plt.xlabel("时间条件")
plt.title("不同样本类型相对理论链路时延的误差分布")
plt.xticks(base_positions, ["正常", "注入时延"])

# 添加简洁图例
from matplotlib.patches import Patch
legend_handles = [
    Patch(facecolor="#4C72B0", alpha=0.8, label="正常-syn"),
    Patch(facecolor="#6C8EBF", alpha=0.8, label="正常-b2b"),
    Patch(facecolor="#8CA7CF", alpha=0.8, label="正常-data"),
    Patch(facecolor="#DD8452", alpha=0.8, label="注入时延-syn"),
    Patch(facecolor="#E49A73", alpha=0.8, label="注入时延-b2b"),
    Patch(facecolor="#EBB194", alpha=0.8, label="注入时延-data"),
]
plt.legend(handles=legend_handles, ncol=2)

plt.tight_layout()
plt.savefig(fig_box, dpi=300, bbox_inches="tight")
plt.show()

print(f"箱线图已保存到: {fig_box}")