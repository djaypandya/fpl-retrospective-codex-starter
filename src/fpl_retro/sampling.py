"""Sampling helpers for top-N manager cohorts."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class RankBand:
    """Inclusive rank interval used for stratified sampling."""

    label: str
    lower: int
    upper: int


DEFAULT_TOP_80K_RANK_BANDS = (
    RankBand("1-1k", 1, 1_000),
    RankBand("1k-5k", 1_001, 5_000),
    RankBand("5k-10k", 5_001, 10_000),
    RankBand("10k-20k", 10_001, 20_000),
    RankBand("20k-40k", 20_001, 40_000),
    RankBand("40k-80k", 40_001, 80_000),
)


def assign_rank_band(
    df: pd.DataFrame,
    *,
    rank_column: str = "overall_rank",
    bands: tuple[RankBand, ...] = DEFAULT_TOP_80K_RANK_BANDS,
) -> pd.DataFrame:
    """Return a copy of ``df`` with a categorical ``rank_band`` column."""

    output = df.copy()
    output[rank_column] = output[rank_column].astype(int)
    output["rank_band"] = pd.NA

    for band in bands:
        in_band = output[rank_column].between(band.lower, band.upper, inclusive="both")
        output.loc[in_band, "rank_band"] = band.label

    band_order = [band.label for band in bands]
    output["rank_band"] = pd.Categorical(output["rank_band"], categories=band_order, ordered=True)
    return output


def allocate_stratified_sample(
    band_counts: pd.Series,
    sample_size: int,
    *,
    minimum_per_band: int = 0,
) -> pd.Series:
    """Allocate ``sample_size`` proportionally across rank bands.

    The allocation is deterministic, never exceeds available rows in a band,
    gives any rounding remainder to bands with the largest fractional
    remainders, and can enforce a minimum per non-empty band.
    """

    if sample_size <= 0:
        raise ValueError("sample_size must be positive")

    counts = band_counts[band_counts > 0].astype(int)
    available = int(counts.sum())
    if available == 0:
        raise ValueError("no candidates available for sampling")
    if sample_size > available:
        raise ValueError(f"sample_size {sample_size} exceeds available candidates {available}")
    if minimum_per_band < 0:
        raise ValueError("minimum_per_band cannot be negative")
    minimum_required = int(counts.clip(upper=minimum_per_band).sum())
    if minimum_required > sample_size:
        raise ValueError(
            f"minimum_per_band requires {minimum_required} rows, exceeding sample_size {sample_size}"
        )

    raw = counts / available * sample_size
    allocation = raw.astype(int)
    remainder = sample_size - int(allocation.sum())

    if remainder:
        fractions = (raw - allocation).sort_values(ascending=False)
        for band_label in fractions.index[:remainder]:
            allocation.loc[band_label] += 1

    overfull = allocation > counts
    if overfull.any():
        surplus = int((allocation[overfull] - counts[overfull]).sum())
        allocation[overfull] = counts[overfull]
        capacity = counts - allocation
        for band_label in capacity.sort_values(ascending=False).index:
            if surplus == 0:
                break
            add = min(int(capacity.loc[band_label]), surplus)
            allocation.loc[band_label] += add
            surplus -= add

    if minimum_per_band:
        minimums = counts.clip(upper=minimum_per_band)
        shortfalls = (minimums - allocation).clip(lower=0)
        extra_needed = int(shortfalls.sum())
        allocation = allocation.add(shortfalls, fill_value=0).astype(int)

        while extra_needed > 0:
            donor_capacity = allocation - minimums
            donor_capacity = donor_capacity[donor_capacity > 0].sort_values(ascending=False)
            if donor_capacity.empty:
                raise ValueError("could not rebalance sample allocation to satisfy minimum_per_band")
            donor_band = donor_capacity.index[0]
            allocation.loc[donor_band] -= 1
            extra_needed -= 1

    return allocation.astype(int)


def create_rank_stratified_sample(
    candidates: pd.DataFrame,
    *,
    sample_size: int,
    random_seed: int,
    my_team_id: int,
    manager_column: str = "manager_id",
    rank_column: str = "overall_rank",
    bands: tuple[RankBand, ...] = DEFAULT_TOP_80K_RANK_BANDS,
    minimum_per_band: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create a reproducible rank-stratified sample and distribution table."""

    required_columns = {manager_column, rank_column}
    missing_columns = required_columns - set(candidates.columns)
    if missing_columns:
        raise ValueError(f"missing candidate columns: {sorted(missing_columns)}")

    sampled_pool = candidates.copy()
    sampled_pool[manager_column] = sampled_pool[manager_column].astype(int)
    sampled_pool = sampled_pool[sampled_pool[manager_column] != int(my_team_id)].copy()
    sampled_pool = sampled_pool.drop_duplicates(subset=[manager_column], keep="first")
    sampled_pool = assign_rank_band(sampled_pool, rank_column=rank_column, bands=bands)
    sampled_pool = sampled_pool[sampled_pool["rank_band"].notna()].copy()

    band_counts = sampled_pool["rank_band"].value_counts(sort=False)
    allocation = allocate_stratified_sample(
        band_counts,
        sample_size,
        minimum_per_band=minimum_per_band,
    )

    sampled_frames = []
    for band_label, n_rows in allocation.items():
        band_rows = sampled_pool[sampled_pool["rank_band"] == band_label]
        sampled_frames.append(band_rows.sample(n=int(n_rows), random_state=random_seed))

    sample_df = pd.concat(sampled_frames, ignore_index=True)
    sample_df = sample_df.sort_values([rank_column, manager_column]).reset_index(drop=True)

    distribution = (
        sampled_pool["rank_band"]
        .value_counts(sort=False)
        .rename("candidate_count")
        .to_frame()
        .join(sample_df["rank_band"].value_counts(sort=False).rename("sample_count"))
        .fillna({"sample_count": 0})
        .reset_index(names="rank_band")
    )
    distribution["sample_count"] = distribution["sample_count"].astype(int)
    distribution["candidate_share"] = distribution["candidate_count"] / distribution["candidate_count"].sum()
    distribution["sample_share"] = distribution["sample_count"] / distribution["sample_count"].sum()

    return sample_df, distribution
