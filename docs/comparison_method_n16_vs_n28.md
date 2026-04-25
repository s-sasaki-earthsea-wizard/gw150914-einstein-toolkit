# 解像度差を吸収する N=16 vs N=28 比較手法 (Stage A 100 M)

本ドキュメントは Phase 4 Stage A 比較 (Issue #4 タスク B1) で採用する
**自前 N=16 run** vs **Zenodo N=28 reference** の比較戦略を定義する。
`scripts/analyze/compare_stage_a.py` の設計根拠 + go/no-go 判定基準の
出典として運用する。

## 1. 前提と制約

### 1.1 解像度差

| | N=28 (Zenodo) | N=16 (自前) | 比 |
| --- | ---: | ---: | ---: |
| 空間刻み h₀ | 1.224 M | 2.143 M | 1.75 |
| 時間刻み dt_it | 0.00215 M | 0.00375 M | 1.75 |
| Carpet level-1 buffer 厚 | ~6 M | ~10.7 M | 1.75 |
| sphere_inner_radius | 51.40 M | 77.10 M | 1.50 |

**同じ initial data・同じ rpar 構造**で空間/時間刻みのみ 1.75 倍粗い。
詳細は [Phase 3b-ii メモ (CLAUDE.md)] および
[Issue #9](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/9)
参照。

### 1.2 古典的 convergence test を採らない理由

数値相対論で標準的な検証は **3 解像度での Richardson extrapolation
convergence test** (低/中/高 解像度を別 run で取り、収束次数 p を求める)
だが、本プロジェクトは:

- 16 コア環境制約: 1 run あたり最低 1 日 (Stage A) を要し、3 解像度は予算外
- 教育目的: 公式 GW150914 イベントを "試しに動かす" のが主眼であり、
  論文クラスの数値検証は要求されない

→ **pointwise X% 以内の weak validation** で代替する。
Stage A pass は「N=16 が物理的に正しい方向に進んでいる」ことを確認する
sanity check であり、「N=16 の数値解が N=28 と区別できないほど精度が高い」
ことの主張ではない。

## 2. 比較 3 層

| 層 | 内容 | 主な目的 | 出力形式 |
| --- | --- | --- | --- |
| **(a) 時系列重ね描き** | 同 cctk_time 軸で N=16 / N=28 を重ねる | 定性的に同じ物理 (軌道、減衰、波形) を辿っているか目視確認 | matplotlib plot |
| **(b) スナップショット値** | t=100 M 時点の単一値比較 | 数値的 pass/fail 判定 (閾値 ± X%) | JSON + コンソール |
| **(c) 自己整合 (self-consistency)** | N=16 単体でのドリフト評価 | Zenodo に対応データがない量 (Hamiltonian constraint, mass drift) の検証 | JSON + plot |

### 2.1 (a) 時系列重ね描き

主要プロット (Stage A):

| 図 | 縦軸 | 横軸 | 備考 |
| --- | --- | --- | --- |
| 軌道分離 | D(t) [M] | cctk_time [M] | BH_diagnostics centroid から計算 |
| 角運動量変化 | m_irreducible(t) | cctk_time | 物理保存量 (inspiral 早期は ほぼ一定) |
| 無次元スピン | χ(t) = J/M_h² | cctk_time | 同上 |
| ψ4 実部 | Re ψ4₂₂(t) at r=100 M | cctk_time | 因果的に届く最近接 sphere |
| ψ4 振幅 | \|ψ4₂₂\|(t) at r=100 M | cctk_time | 同上 |

縦軸は同じ物理単位 (M または無次元) なので、縦軸スケーリングは不要。
ただし時刻軸は両 run とも cctk_time = 0 が initial data なので一致する。

### 2.2 (b) スナップショット pass/fail (Stage A の主判定)

t = 100 M 時点で以下を比較。reference 値 (N=28) と pass 閾値の出典は
[Issue #4](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/4)
の表 (タスク A3+A5 で確定):

| 指標 | N=28 reference | pass 閾値 | 備考 |
| --- | --- | --- | --- |
| クラッシュなし | — | 100 M 完走 | abort_on_io_errors の発火・NaN 出力なし |
| 軌道分離 D | 9.773 M | ±10% (= 8.80–10.75) | 解像度差で軌道がやや進む可能性を考慮 |
| 軌道角 φ | 2.694 rad | ±0.5 rad | atan2(Δy, Δx) |
| BH1 m_irreducible | 0.5470 M | ±2% | 物理保存量 (drift 小) |
| BH2 m_irreducible | 0.4335 M | ±2% | 同上 |
| BH1 horizon mass M_h | 0.5539 M | ±0.5% | 同上 |
| BH2 horizon mass M_h | 0.4462 M | ±0.5% | 同上 |
| BH1 χ₁ = J/M² | +0.3102 | ±0.005 | 物理保存量 (N=28 drift < 3e-4) |
| BH2 χ₂ = J/M² | -0.4604 | ±0.005 | 同上 |
| ψ4₂₂ phase at r=100 M | -0.674 rad | ±0.5 rad | 位相は解像度差で 1 rad 程度ずれうる |
| ψ4₂₂ \|amplitude\| at r=100 M | 1.67e-5 | **±50% (暫定)** | §4 参照、Stage A 後にチューニング |

#### 閾値根拠の整理

- **質量・スピン (±0.5%, ±0.005)**: inspiral 早期は物理的にほぼ保存。
  Zenodo N=28 自身の 0–100 M ドリフトが m_h < 0.05%, χ < 3e-4 なので、
  N=16 でドリフトが 1 桁悪化しても pass する余裕。
- **m_irreducible (±2%)**: m_h より測定ノイズが大きい (areal radius 経由)
  ため緩めに設定。
- **D (±10%)**: 解像度差で軌道がやや早く/遅く進む可能性。inspiral 後期
  ほどズレが拡大するが、t=100 M (~1 軌道強) では 10% で十分。
- **位相 (±0.5 rad)**: 解像度差は主に位相に出る。0.5 rad ≈ 28°は
  inspiral 全体での累積位相 (~10 rad) の 5%。
- **振幅 (±50% 暫定)**: §4 参照。

### 2.3 (c) 自己整合 (Zenodo 比較不可項目)

[A2 の発見] により Zenodo に **Hamiltonian / Momentum constraint norm
出力がない**ことが判明。これらは N=16 自前 run の self-consistency
検証として実施する:

| 項目 | pass 閾値 | 備考 |
| --- | --- | --- |
| Hamiltonian L2 norm | 80–100 M で発散していない | 要 B2: rpar に constraint 出力有効化 |
| m_irreducible 時間ドリフト | 0–100 M で max-min < 1% | 単一 run 内 |
| χ 時間ドリフト | 0–100 M で max-min < 0.01 | N=28 では 3e-4 |

(B2 = constraint 出力有効化は Phase 3c-2 投入前に別ブランチで対応予定)

## 3. ψ4 retarded time alignment

### 3.1 因果性問題

ψ4 は球面 r で抽出される量で、initial data が放射した重力波が
半径 r に到達する時刻はおよそ:

```
t_arrival ≈ r  (M=1 単位、c=1 自然単位)
```

Stage A は t=100 M で評価するため、抽出半径との関係は:

| 半径 r [M] | t=100 における波の到達状況 | 振幅オーダー |
| ---: | --- | --- |
| 100 | ぎりぎり到達 (t ≈ r) | 1.67e-5 (実測) |
| 115 | 未到達 (t < r) | 桁落ち |
| 136 | 未到達 | 桁落ち |
| 167 | 未到達 | 桁落ち |
| 214 | 未到達 | 桁落ち |
| 300 | 未到達 (実測 7e-10 — 純粋にゲージモード残差) | ~1e-9 |
| 500 | 未到達 | ~1e-10 |

→ Stage A の振幅・位相比較は **r=100 M (因果的に届く最近接)** を
**主**判定とし、他半径は時系列重ね描きの参考表示にとどめる。

### 3.2 retarded time の式

複数半径で観測波形を比較する場合は retarded time:

```
t_ret = t - r
```

で揃えると、同じ initial data 由来の波として重なる (ただし振幅は
r⁻¹ で減衰する別問題)。Stage B/C で複数半径の振幅減衰検証を
実施する場合、この補正が必須。Stage A では r=100 のみ使うので
本書では実装方針のみ記載し、実装は Stage B 段階で追加する。

実装方針:
```python
def shift_to_retarded(t: np.ndarray, signal: np.ndarray, r: float):
    return t - r, signal  # 単純シフト (n_samples は変わらない)
```

## 4. ψ4 振幅 pass 閾値の暫定方針

### 4.1 なぜ「暫定 ±50%」なのか

- 解像度を 1.75 倍粗くすると、空間 4 階微分を含む ψ4 (Weyl scalar) は
  最も精度が落ちやすい量
- 過去の文献 (e.g., Boyle+ 2007) では convergence order p ≈ 4 の
  finite difference scheme で h を 1.75 倍粗くすると ψ4 振幅誤差は
  概ね 1.75⁴ ≈ 9 倍 → と単純評価できるが、AMR + 多重パッチでは
  実効 p < 4 になりがち
- 経験則として ψ4 振幅は N=16 で N=28 比 30–50% 落ちる可能性 (現時点で
  本プロジェクトの実測なし)

→ **±50% で開始**し、Stage A 完走後に N=16 実測値を見て
**Stage B/C 用に再チューニング**する。Stage A 自体の pass/fail には
この閾値を使わず、暫定値として出力 JSON にのみ記録する設計を採る
(§5 参照)。

### 4.2 振幅 ±50% の意味

```
0.5 × 1.67e-5 ≤ |ψ4_22 N=16(r=100, t=100)| ≤ 1.5 × 1.67e-5
0.835e-5     ≤                                ≤ 2.51e-5
```

この範囲内なら "波形の概形は出ている" と判断。範囲外でも
時系列プロットで波形が見えていれば go と判定する余地あり。

## 5. Stage A pass/fail JSON スキーマ

`scripts/analyze/compare_stage_a.py` 出力は以下の形式:

```json
{
  "stage": "A",
  "target_time_M": 100.0,
  "n16_dir": "simulations/GW150914_n16",
  "n28_dir": "data/GW150914_N28_zenodo/extracted/GW150914_28",
  "overall_pass": true,
  "checks": {
    "completion": {
      "pass": true,
      "details": "n16 reached t=100.5 M without crash"
    },
    "separation_D": {
      "pass": true,
      "n16": 9.812,
      "n28": 9.773,
      "delta_pct": 0.40,
      "threshold_pct": 10.0
    },
    "horizon_mass_bh1": { ... },
    "chi_bh1": { ... },
    "psi4_22_phase": { ... },
    "psi4_22_amplitude": {
      "pass": null,                       // 暫定閾値のため pass/fail 判定対象外
      "n16": 1.42e-5,
      "n28": 1.67e-5,
      "delta_pct": -15.0,
      "threshold_pct": 50.0,
      "note": "provisional threshold, not counted in overall_pass"
    }
  },
  "self_consistency": {
    "m_irreducible_drift_bh1": { "pass": true, "drift_pct": 0.34, "threshold_pct": 1.0 },
    "chi_drift_bh1": { "pass": true, "drift": 0.0008, "threshold": 0.01 }
  }
}
```

`overall_pass` は `checks.*.pass != false` (= true または null) かつ
`self_consistency.*.pass == true` で算出。`null` は判定対象外
(暫定閾値) を意味する。

## 6. Stage B/C への申し送り

- 振幅閾値の最終チューニング (Stage A 実測 + Boyle+2007 等の文献ベース)
- merger 時刻判定: |ψ4₂₂| ピーク時刻 (公式 N=28: 899 M ± 5%)
- ringdown QNM 周波数フィット (Stage C のみ)
- 複数抽出半径での retarded time alignment (§3.2 の実装)

## 関連 Issue / ドキュメント

- [Issue #4 — Phase 4 軌道・波形プロット](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/4)
- [Issue #3 — Phase 3c N=16 production](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/3)
- [Issue #9 — Phase 3b-ii N=16 grid 改変](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/9)
- `CLAUDE.md` Phase 3b-ii / 3c-1 / 4 メモ
- `.claude-notes/2026-04-25_phase4-stage-a-prep.md` (A1-A5 一次調査)
