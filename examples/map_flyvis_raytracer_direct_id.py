from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent

FLYVIS_PATH = BASE_DIR / "flyvis_native_input_mapping_extent15.csv"
RAYTRACER_PATH = BASE_DIR / "raytracer_frame_1.csv"

OUT_PATH = BASE_DIR / "flyvis_raytracer_direct_id_mapped_frame_1.csv"
MISSING_PATH = BASE_DIR / "flyvis_raytracer_direct_id_missing_frame_1.csv"


# Output table after direct-ID mapping.
# direct-ID 映射之后的输出表。
OUT_PATH = Path("flyvis_raytracer_direct_id_mapped_frame_1.csv")

# Rows that could not be matched.
# 没有匹配成功的行。
MISSING_PATH = Path("flyvis_raytracer_direct_id_missing_frame_1.csv")


def main() -> None:
    # -----------------------------
    # 1. Load both tables / 读取两个表
    # -----------------------------
    # FlyVis table columns:
    #   hexal_id, receptor_channel, node_id, node_type, u, v
    # FlyVis 表包含：
    #   hexal_id, receptor_channel, node_id, node_type, u, v
    flyvis = pd.read_csv(FLYVIS_PATH)

    # Raytracer table columns:
    #   frame_id, global_indices, lens_indices, receptor_type,
    #   position_x/y/z_um, direction_x/y/z, colours_r_uv/g/b, intensity
    # Raytracer 表包含：
    #   frame_id, global_indices, lens_indices, receptor_type,
    #   position_x/y/z_um, direction_x/y/z, colours_r_uv/g/b, intensity
    raytracer = pd.read_csv(RAYTRACER_PATH)

    # -----------------------------
    # 2. Define the direct-ID mapping rule / 定义 direct-ID 映射规则
    # -----------------------------
    # Current assumption:
    #   FlyVis hexal_id         == Raytracer lens_indices
    #   FlyVis receptor_channel 0..6 == Raytracer receptor_type 0..6
    #   FlyVis receptor_channel 7    == Raytracer receptor_type 6
    #
    # 当前假设：
    #   FlyVis 的 hexal_id         等于 Raytracer 的 lens_indices
    #   FlyVis 的 receptor_channel 0..6 对应 Raytracer receptor_type 0..6
    #   FlyVis 的 receptor_channel 7（R8）复用 Raytracer receptor_type 6（R7）
    #
    # Important:
    # This is only a simple pipeline-test mapping. It does not prove that the
    # two systems use the same biological/geometrical ordering.
    #
    # 注意：
    # 这只是一个用于测试流程的简单映射。它不能证明两个系统的编号在生物/几何上
    # 一定完全对应。

    # FlyVis has 721 hexal positions: 0..720.
    # Raytracer has more ommatidia, so we only keep raytracer ommatidia whose
    # IDs exist in the FlyVis table.
    #
    # FlyVis 有 721 个 hexal 位置：0..720。
    # Raytracer 的 ommatidia 更多，所以这里只保留 Raytracer 中 ID 能在
    # FlyVis 表里找到的那一部分。
    flyvis_hexal_ids = flyvis["hexal_id"].unique()
    raytracer_subset = raytracer[
        raytracer["lens_indices"].isin(flyvis_hexal_ids)
    ].copy()

    # The raytracer currently provides seven receptor types (0..6), whereas
    # FlyVis has eight receptor channels (0..7). R7 and R8 are stacked and
    # look at the same point, so FlyVis channel 7 reuses raytracer type 6.
    #
    # Raytracer 当前有 7 个 receptor type（0..6），FlyVis 有 8 个 receptor
    # channel（0..7）。由于 R7 和 R8 上下叠置并看向同一点，因此 FlyVis
    # channel 7 复用 Raytracer type 6。
    flyvis["raytracer_receptor_type"] = flyvis["receptor_channel"].clip(upper=6)

    # -----------------------------
    # 3. Merge the tables / 合并两个表
    # -----------------------------
    # left_on:
    #   FlyVis columns used as keys.
    # right_on:
    #   Raytracer columns used as keys.
    #
    # left_on:
    #   FlyVis 用来匹配的列。
    # right_on:
    #   Raytracer 用来匹配的列。
    #
    # how="left" means:
    #   Keep every FlyVis input row, even if there is no matching raytracer row.
    #
    # how="left" 表示：
    #   保留每一个 FlyVis 输入行，即使它在 Raytracer 表里没有匹配项。
    mapped = flyvis.merge(
        raytracer_subset,
        left_on=["hexal_id", "raytracer_receptor_type"],
        right_on=["lens_indices", "receptor_type"],
        how="left",
        indicator=True,
    )

    # The merge indicator says whether each row was matched.
    # merge indicator 用来标记每一行是否匹配成功。
    mapped["matched"] = mapped["_merge"].eq("both")
    mapped = mapped.drop(columns=["_merge"])

    # -----------------------------
    # 4. Use the raytracer intensity / 使用 Raytracer 的 intensity
    # -----------------------------
    # The new raytracer table already contains:
    #
    #   intensity = mean(colours_r_uv, colours_g, colours_b)
    #
    # Therefore no additional RGB conversion is needed here.
    #
    # 新 Raytracer 表已经包含：
    #
    #   intensity = mean(colours_r_uv, colours_g, colours_b)
    #
    # 因此这里不再重复计算 RGB 平均值。

    # -----------------------------
    # 5. Reorder columns / 调整列顺序
    # -----------------------------
    # Put FlyVis identity columns first, then raytracer identity/geometric/color
    # columns, then the matched flag.
    #
    # 先放 FlyVis 的身份信息，再放 Raytracer 的身份/几何/RGB 信息，最后放
    # matched 标记。
    columns = [
        "hexal_id",
        "receptor_channel",
        "raytracer_receptor_type",
        "node_id",
        "node_type",
        "u",
        "v",
        "frame_id",
        "global_indices",
        "lens_indices",
        "receptor_type",
        "position_x_um",
        "position_y_um",
        "position_z_um",
        "direction_x",
        "direction_y",
        "direction_z",
        "colours_r_uv",
        "colours_g",
        "colours_b",
        "intensity",
        "matched",
    ]
    mapped = mapped[[col for col in columns if col in mapped.columns]]

    # -----------------------------
    # 6. Save outputs / 保存结果
    # -----------------------------
    # Full mapped table.
    # 完整映射表。
    mapped.to_csv(OUT_PATH, index=False)

    # Rows that were not matched.
    # 没有匹配成功的行。
    missing = mapped[~mapped["matched"]]
    missing.to_csv(MISSING_PATH, index=False)

    # -----------------------------
    # 7. Print a short report / 打印简短报告
    # -----------------------------
    print(f"FlyVis rows: {len(flyvis)}")
    print(f"Raytracer rows: {len(raytracer)}")
    print(f"Raytracer subset rows: {len(raytracer_subset)}")
    print(f"Mapped rows: {len(mapped)}")
    print(f"Matched rows: {int(mapped['matched'].sum())}")
    print(f"Missing rows: {int((~mapped['matched']).sum())}")
    print()
    print("Missing rows by FlyVis receptor_channel:")
    print(missing["receptor_channel"].value_counts().sort_index())
    print()
    print(f"Saved mapped table: {OUT_PATH}")
    print(f"Saved missing table: {MISSING_PATH}")


if __name__ == "__main__":
    main()
