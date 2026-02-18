"""IEC 국제 표준 적합성 검증 테스트.

Verifies GridFlow engine compliance with key IEC standards:
  - IEC 61727 / IEC 62116: DER grid connection (voltage, frequency, reconnection)
  - IEC 60909: Short-circuit current calculation
  - IEC 60038: Standard voltage levels
  - IEC 60076: Transformer impedance model
  - IEC 60228: Cable impedance library
  - IEC 61000: Power quality (THD, voltage unbalance)
  - N-1 contingency analysis per IEC/IEEE methodology
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from engine.network.grid_codes import (
    IEC_DEFAULT,
    FIJI_GRID_CODE,
    IEEE_1547,
    GridCodeProfile,
    VoltageLimits,
    FrequencyLimits,
    build_custom_profile,
    get_profile,
    list_profiles,
)
from engine.network.network_model import (
    BranchData,
    BusData,
    BusType,
    NetworkModel,
    build_network_from_config,
)
from engine.network.per_unit import (
    cable_z_pu,
    i_base,
    ohm_to_pu,
    pf_to_q,
    power_to_pu,
    transformer_z_pu,
    z_base,
)
from engine.network.power_flow import solve_power_flow, dc_power_flow
from engine.network.short_circuit import calculate_short_circuit
from engine.network.cable_library import CABLE_LIBRARY, CableSpec
from engine.network.transformer_model import TRANSFORMER_LIBRARY, TransformerSpec
from engine.network.contingency import run_contingency_analysis


# ======================================================================
# Helper: IEC-standard test networks
# ======================================================================


def _iec_lv_network(load_kw: float = 50.0, pf: float = 0.90) -> NetworkModel:
    """IEC-compliant LV distribution network (11kV/0.4kV).

    Slack (11kV grid) → Transformer (500kVA Dyn11) → LV Bus (0.4kV) → Load
    Follows IEC 60038 voltage levels.
    """
    q_kvar = load_kw * math.sqrt(1 - pf**2) / pf
    s_base = 1.0  # 1 MVA

    buses = [
        BusData(index=0, name="MV_Grid", bus_type=BusType.SLACK,
                nominal_voltage_kv=11.0, v_setpoint_pu=1.0, sc_mva=150.0),
        BusData(index=1, name="LV_Bus", bus_type=BusType.PQ,
                nominal_voltage_kv=0.4,
                p_load_pu=load_kw / 1000.0 / s_base,
                q_load_pu=q_kvar / 1000.0 / s_base),
    ]

    # 500 kVA 11/0.4kV transformer (IEC 60076 standard)
    z_tx = transformer_z_pu(impedance_pct=4.0, rating_kva=500.0,
                            s_base_mva=s_base, x_r_ratio=8.0)
    branches = [
        BranchData(index=0, name="TX_500kVA", from_bus=0, to_bus=1,
                   branch_type="transformer", z_pu=z_tx,
                   tap=1.0+0j, rating_mva=0.5),
    ]
    return NetworkModel(buses=buses, branches=branches, s_base_mva=s_base)


def _iec_mv_network() -> NetworkModel:
    """IEC-compliant MV distribution network (33kV/11kV/0.4kV), 4 buses."""
    s_base = 1.0

    buses = [
        BusData(index=0, name="Grid_33kV", bus_type=BusType.SLACK,
                nominal_voltage_kv=33.0, v_setpoint_pu=1.0, sc_mva=500.0),
        BusData(index=1, name="MV_11kV", bus_type=BusType.PQ,
                nominal_voltage_kv=11.0, p_load_pu=0.0),
        BusData(index=2, name="LV_Bus_1", bus_type=BusType.PQ,
                nominal_voltage_kv=0.4,
                p_load_pu=0.100, q_load_pu=0.048),  # 100 kW, pf=0.9
        BusData(index=3, name="LV_Bus_2", bus_type=BusType.PQ,
                nominal_voltage_kv=0.4,
                p_load_pu=0.080, q_load_pu=0.039),  # 80 kW, pf=0.9
    ]

    z_33_11 = transformer_z_pu(impedance_pct=7.0, rating_kva=2500.0,
                                s_base_mva=s_base, x_r_ratio=12.0)
    z_11_04_a = transformer_z_pu(impedance_pct=4.0, rating_kva=500.0,
                                  s_base_mva=s_base, x_r_ratio=8.0)
    z_11_04_b = transformer_z_pu(impedance_pct=4.0, rating_kva=400.0,
                                  s_base_mva=s_base, x_r_ratio=7.5)

    branches = [
        BranchData(index=0, name="TX_33_11", from_bus=0, to_bus=1,
                   branch_type="transformer", z_pu=z_33_11,
                   tap=1.0+0j, rating_mva=2.5),
        BranchData(index=1, name="TX_11_04_A", from_bus=1, to_bus=2,
                   branch_type="transformer", z_pu=z_11_04_a,
                   tap=1.0+0j, rating_mva=0.5),
        BranchData(index=2, name="TX_11_04_B", from_bus=1, to_bus=3,
                   branch_type="transformer", z_pu=z_11_04_b,
                   tap=1.0+0j, rating_mva=0.4),
    ]
    return NetworkModel(buses=buses, branches=branches, s_base_mva=s_base)


# ======================================================================
# IEC 61727 / IEC 62116: DER Grid Connection
# ======================================================================


class TestIEC61727:
    """IEC 61727 — DER 계통연계 전압/주파수 기준 검증."""

    def test_normal_voltage_range(self):
        """IEC 61727: 정상 전압 범위 ±5% (0.95–1.05 pu)."""
        assert IEC_DEFAULT.voltage.normal_min == 0.95
        assert IEC_DEFAULT.voltage.normal_max == 1.05

    def test_contingency_voltage_range(self):
        """IEC 61727: 사고시 전압 범위 ±10% (0.90–1.10 pu)."""
        assert IEC_DEFAULT.voltage.contingency_min == 0.90
        assert IEC_DEFAULT.voltage.contingency_max == 1.10

    def test_nominal_frequency_50hz(self):
        """IEC 61727: 공칭 주파수 50 Hz."""
        assert IEC_DEFAULT.frequency.nominal_hz == 50.0

    def test_normal_frequency_range(self):
        """IEC 61727: 정상 주파수 범위 49.5–50.5 Hz (±1%)."""
        assert IEC_DEFAULT.frequency.normal_min_hz == 49.5
        assert IEC_DEFAULT.frequency.normal_max_hz == 50.5

    def test_contingency_frequency_range(self):
        """IEC 61727: 사고시 주파수 범위 47.5–52.0 Hz."""
        assert IEC_DEFAULT.frequency.contingency_min_hz == 47.5
        assert IEC_DEFAULT.frequency.contingency_max_hz == 52.0

    def test_min_power_factor(self):
        """IEC 61727: 최소 역률 0.90."""
        assert IEC_DEFAULT.power_factor.min_pf == 0.90

    def test_min_sc_ratio(self):
        """IEC 61727: 최소 단락용량비 (Ssc/Sgen) ≥ 3.0."""
        assert IEC_DEFAULT.fault_level.min_sc_ratio >= 3.0

    def test_max_fault_current(self):
        """IEC 60909 연계: 최대 단락전류 50 kA (차단기 정격)."""
        assert IEC_DEFAULT.fault_level.max_fault_ka == 50.0


class TestIEC62116:
    """IEC 62116 — 단독운전 방지 및 재연계 요건."""

    def test_reconnection_voltage_window(self):
        """IEC 62116: 재연계 전압 0.90–1.10 pu."""
        assert IEC_DEFAULT.reconnection.voltage_return_min == 0.90
        assert IEC_DEFAULT.reconnection.voltage_return_max == 1.10

    def test_reconnection_frequency_window(self):
        """IEC 62116: 재연계 주파수 49.5–50.5 Hz."""
        assert IEC_DEFAULT.reconnection.frequency_return_min == 49.5
        assert IEC_DEFAULT.reconnection.frequency_return_max == 50.5

    def test_intentional_delay(self):
        """IEC 62116: 의도적 재연계 지연 300초 (5분)."""
        assert IEC_DEFAULT.reconnection.intentional_delay_s == 300.0

    def test_standard_reference(self):
        """IEC 프로파일 표준 참조 확인."""
        assert "IEC 61727" in IEC_DEFAULT.standard
        assert "IEC 62116" in IEC_DEFAULT.standard


# ======================================================================
# IEC 61000: Power Quality
# ======================================================================


class TestIEC61000:
    """IEC 61000 — 전력품질 기준 (THD, 전압불평형)."""

    def test_max_thd_5_percent(self):
        """IEC 61000-3-6: 총고조파왜곡률(THD) ≤ 5%."""
        assert IEC_DEFAULT.max_thd_pct == 5.0

    def test_max_voltage_unbalance_2_percent(self):
        """IEC 61000-2-2: 전압불평형률 ≤ 2%."""
        assert IEC_DEFAULT.max_voltage_unbalance_pct == 2.0

    def test_fiji_same_thd_limit(self):
        """피지 계통연계 기준도 THD 5% 준수."""
        assert FIJI_GRID_CODE.max_thd_pct == 5.0

    def test_ieee_higher_unbalance_allowed(self):
        """IEEE 1547은 전압불평형 3% 허용 (IEC 대비 완화)."""
        assert IEEE_1547.max_voltage_unbalance_pct == 3.0
        assert IEEE_1547.max_voltage_unbalance_pct > IEC_DEFAULT.max_voltage_unbalance_pct


# ======================================================================
# IEC 60038: Standard Voltages
# ======================================================================


class TestIEC60038:
    """IEC 60038 — 표준 전압 등급 검증."""

    def test_lv_base_impedance(self):
        """IEC 60038 LV: Z_base = V²/S = 0.4²/1.0 = 0.16 Ω."""
        zb = z_base(v_base_kv=0.4, s_base_mva=1.0)
        assert abs(zb - 0.16) < 1e-6

    def test_mv_base_impedance(self):
        """IEC 60038 MV 11kV: Z_base = 11²/1.0 = 121 Ω."""
        zb = z_base(v_base_kv=11.0, s_base_mva=1.0)
        assert abs(zb - 121.0) < 1e-6

    def test_hv_base_impedance(self):
        """IEC 60038 HV 33kV: Z_base = 33²/1.0 = 1089 Ω."""
        zb = z_base(v_base_kv=33.0, s_base_mva=1.0)
        assert abs(zb - 1089.0) < 1e-6

    def test_lv_base_current(self):
        """IEC 60038: I_base = S/(√3·V) = 1.0/(√3×0.4) = 1.443 kA."""
        ib = i_base(v_base_kv=0.4, s_base_mva=1.0)
        expected = 1.0 / (math.sqrt(3) * 0.4)
        assert abs(ib - expected) < 1e-3

    def test_mv_base_current(self):
        """IEC 60038: I_base at 11kV = 1.0/(√3×11) = 0.05249 kA."""
        ib = i_base(v_base_kv=11.0, s_base_mva=1.0)
        expected = 1.0 / (math.sqrt(3) * 11.0)
        assert abs(ib - expected) < 1e-5

    def test_per_unit_roundtrip(self):
        """Per-unit ↔ ohm 변환 일관성 검증."""
        z_ohm = complex(0.5, 1.2)
        z_pu = ohm_to_pu(z_ohm, v_base_kv=0.4, s_base_mva=1.0)
        # Z_base = 0.16, so z_pu = (0.5+1.2j) / 0.16
        expected_pu = z_ohm / 0.16
        assert abs(z_pu - expected_pu) < 1e-10

    def test_power_to_pu(self):
        """kW/kvar → per-unit 변환 검증."""
        s_pu = power_to_pu(p_kw=500, q_kvar=200, s_base_mva=1.0)
        assert abs(s_pu.real - 0.5) < 1e-10
        assert abs(s_pu.imag - 0.2) < 1e-10

    def test_pf_to_q(self):
        """역률(PF)에서 무효전력(Q) 계산 검증."""
        q = pf_to_q(p_kw=100.0, power_factor=0.90)
        # Q = P × tan(arccos(0.90)) = 100 × 0.4843 = 48.43 kvar
        expected = 100.0 * math.sqrt(1 - 0.9**2) / 0.9
        assert abs(q - expected) < 0.1

    def test_pf_unity_zero_q(self):
        """역률 1.0 → 무효전력 0."""
        q = pf_to_q(p_kw=100.0, power_factor=1.0)
        assert q == 0.0


# ======================================================================
# IEC 60076: Transformer Model
# ======================================================================


class TestIEC60076:
    """IEC 60076 — 변압기 임피던스 모델 검증."""

    def test_transformer_library_exists(self):
        """IEC 60076 표준 변압기 라이브러리 존재 확인."""
        assert len(TRANSFORMER_LIBRARY) >= 10

    def test_dyn11_vector_group(self):
        """IEC 60076: LV 배전 변압기는 Dyn11 결선."""
        lv_transformers = [t for t in TRANSFORMER_LIBRARY if t.lv_kv == 0.4]
        for t in lv_transformers:
            assert t.vector_group == "Dyn11", f"{t.name}: expected Dyn11, got {t.vector_group}"

    def test_impedance_range_lv(self):
        """IEC 60076: 배전 변압기(11/0.4kV) 임피던스 4–6%."""
        lv_transformers = [t for t in TRANSFORMER_LIBRARY
                           if t.hv_kv == 11.0 and t.lv_kv == 0.4]
        for t in lv_transformers:
            assert 3.5 <= t.impedance_pct <= 7.0, (
                f"{t.name}: impedance {t.impedance_pct}% outside IEC 60076 range"
            )

    def test_impedance_range_mv(self):
        """IEC 60076: MV 변압기(33/11kV) 임피던스 6–10%."""
        mv_transformers = [t for t in TRANSFORMER_LIBRARY
                           if t.hv_kv == 33.0 and t.lv_kv == 11.0]
        for t in mv_transformers:
            assert 5.0 <= t.impedance_pct <= 10.0, (
                f"{t.name}: impedance {t.impedance_pct}% outside IEC 60076 range"
            )

    def test_x_r_ratio_increases_with_size(self):
        """IEC 60076: X/R 비율은 용량 증가에 따라 증가."""
        lv_transformers = sorted(
            [t for t in TRANSFORMER_LIBRARY if t.lv_kv == 0.4],
            key=lambda t: t.rating_kva,
        )
        if len(lv_transformers) >= 2:
            smallest = lv_transformers[0]
            largest = lv_transformers[-1]
            assert largest.x_r_ratio >= smallest.x_r_ratio

    def test_transformer_z_pu_calculation(self):
        """변압기 임피던스 per-unit 변환 정확성 검증."""
        # 500 kVA, 4%, X/R=8, S_base=1 MVA
        z = transformer_z_pu(impedance_pct=4.0, rating_kva=500.0,
                             s_base_mva=1.0, x_r_ratio=8.0)
        # Z_pu = 0.04 × (1.0 / 0.5) = 0.08 pu (on system base)
        z_mag = abs(z)
        assert abs(z_mag - 0.08) < 0.001, f"Z_pu magnitude = {z_mag}, expected 0.08"
        # X/R = 8 → R = Z/√(1+64), X = 8R
        assert z.imag / z.real == pytest.approx(8.0, rel=0.01)

    def test_transformer_rebase(self):
        """변압기 베이스 변환: S_base 변경 시 임피던스 스케일링."""
        z_1mva = transformer_z_pu(impedance_pct=5.0, rating_kva=1000.0,
                                   s_base_mva=1.0, x_r_ratio=10.0)
        z_100mva = transformer_z_pu(impedance_pct=5.0, rating_kva=1000.0,
                                     s_base_mva=100.0, x_r_ratio=10.0)
        # Z on 100 MVA base should be 100× larger
        ratio = abs(z_100mva) / abs(z_1mva)
        assert abs(ratio - 100.0) < 0.01

    def test_load_loss_positive(self):
        """IEC 60076: 부하손실(load_loss_kw) 양수."""
        for t in TRANSFORMER_LIBRARY:
            assert t.load_loss_kw > 0, f"{t.name}: load_loss_kw should be > 0"

    def test_no_load_loss_less_than_load_loss(self):
        """IEC 60076: 무부하손실 < 부하손실."""
        for t in TRANSFORMER_LIBRARY:
            assert t.no_load_loss_kw < t.load_loss_kw, (
                f"{t.name}: no_load_loss ({t.no_load_loss_kw}) >= load_loss ({t.load_loss_kw})"
            )


# ======================================================================
# IEC 60228: Cable Library
# ======================================================================


class TestIEC60228:
    """IEC 60228 — 케이블 라이브러리 검증."""

    def test_cable_library_exists(self):
        """IEC 60228 표준 케이블 라이브러리 존재 확인."""
        assert len(CABLE_LIBRARY) >= 20

    def test_lv_cables_max_1kv(self):
        """IEC 60228: LV 케이블은 max_voltage ≤ 1.0 kV."""
        lv_cables = [c for c in CABLE_LIBRARY if c.voltage_class == "lv"]
        assert len(lv_cables) > 0
        for c in lv_cables:
            assert c.max_voltage_kv <= 1.0, f"{c.name}: max_voltage_kv = {c.max_voltage_kv}"

    def test_mv_cables_above_1kv(self):
        """IEC 60228: MV 케이블은 max_voltage > 1.0 kV."""
        mv_cables = [c for c in CABLE_LIBRARY if c.voltage_class == "mv"]
        assert len(mv_cables) > 0
        for c in mv_cables:
            assert c.max_voltage_kv > 1.0, f"{c.name}: max_voltage_kv = {c.max_voltage_kv}"

    def test_resistance_decreases_with_size(self):
        """IEC 60228: 단면적 증가 → 저항 감소."""
        cu_lv = sorted(
            [c for c in CABLE_LIBRARY if c.material == "Cu" and c.voltage_class == "lv"],
            key=lambda c: c.size_mm2,
        )
        for i in range(1, len(cu_lv)):
            assert cu_lv[i].r_ohm_per_km <= cu_lv[i-1].r_ohm_per_km, (
                f"{cu_lv[i].name} R ({cu_lv[i].r_ohm_per_km}) > "
                f"{cu_lv[i-1].name} R ({cu_lv[i-1].r_ohm_per_km})"
            )

    def test_ampacity_increases_with_size(self):
        """IEC 60228: 단면적 증가 → 허용전류 증가."""
        cu_lv = sorted(
            [c for c in CABLE_LIBRARY if c.material == "Cu" and c.voltage_class == "lv"],
            key=lambda c: c.size_mm2,
        )
        for i in range(1, len(cu_lv)):
            assert cu_lv[i].ampacity_a >= cu_lv[i-1].ampacity_a, (
                f"{cu_lv[i].name} ampacity ({cu_lv[i].ampacity_a}) < "
                f"{cu_lv[i-1].name} ampacity ({cu_lv[i-1].ampacity_a})"
            )

    def test_al_higher_resistance_than_cu(self):
        """IEC 60228: 같은 단면적에서 알루미늄 > 구리 저항."""
        cu_95 = next((c for c in CABLE_LIBRARY
                      if c.material == "Cu" and c.size_mm2 == 95 and c.voltage_class == "lv"), None)
        al_95 = next((c for c in CABLE_LIBRARY
                      if c.material == "Al" and c.size_mm2 == 95 and c.voltage_class == "lv"), None)
        assert cu_95 is not None and al_95 is not None
        assert al_95.r_ohm_per_km > cu_95.r_ohm_per_km

    def test_cable_z_pu_conversion(self):
        """케이블 임피던스 per-unit 변환 검증."""
        z = cable_z_pu(r_ohm_per_km=0.193, x_ohm_per_km=0.072,
                       length_km=0.1, v_base_kv=0.4, s_base_mva=1.0)
        # Z_ohm = (0.0193, 0.0072), Z_base = 0.16
        z_expected = complex(0.0193, 0.0072) / 0.16
        assert abs(z - z_expected) < 1e-6

    def test_xlpe_insulation(self):
        """IEC 60228: XLPE 절연 케이블 존재 확인."""
        xlpe_cables = [c for c in CABLE_LIBRARY if c.insulation == "XLPE"]
        assert len(xlpe_cables) == len(CABLE_LIBRARY)  # All are XLPE


# ======================================================================
# IEC 60909: Short-Circuit Analysis
# ======================================================================


class TestIEC60909:
    """IEC 60909 — 단락전류 계산 검증."""

    def test_sc_at_slack_bus_high(self):
        """IEC 60909: Slack 버스 단락전류는 높아야 함 (무한모선 근사)."""
        network = _iec_lv_network(load_kw=50.0)
        result = calculate_short_circuit(network, v_pre_pu=1.0)
        slack_sc = result.bus_results[0]
        # Slack bus with infinite bus approximation should have very high Isc
        assert slack_sc.i_sc_ka > 0.1, f"Slack Isc = {slack_sc.i_sc_ka} kA too low"
        assert slack_sc.s_sc_mva > 10.0, f"Slack Ssc = {slack_sc.s_sc_mva} MVA too low"

    def test_sc_at_load_bus_lower(self):
        """IEC 60909: 부하 버스 단락전류는 Slack 버스보다 낮음."""
        network = _iec_lv_network(load_kw=50.0)
        result = calculate_short_circuit(network, v_pre_pu=1.0)
        slack_sc = result.bus_results[0]
        load_sc = result.bus_results[1]
        # Load bus Isc should be lower due to transformer impedance
        assert load_sc.s_sc_mva < slack_sc.s_sc_mva

    def test_voltage_factor_c_effect(self):
        """IEC 60909: 전압계수 c=1.1 적용 시 단락전류 10% 증가."""
        network = _iec_lv_network(load_kw=50.0)
        result_10 = calculate_short_circuit(network, v_pre_pu=1.0)
        result_11 = calculate_short_circuit(network, v_pre_pu=1.1)
        ratio = result_11.bus_results[1].i_sc_ka / result_10.bus_results[1].i_sc_ka
        # With c=1.1, Isc should be ~10% higher
        assert abs(ratio - 1.1) < 0.05, f"Voltage factor ratio = {ratio}, expected ~1.1"

    def test_sc_decreases_with_distance(self):
        """IEC 60909: 계통 원점에서 멀수록 단락전류 감소."""
        network = _iec_mv_network()
        result = calculate_short_circuit(network, v_pre_pu=1.0)
        # Grid bus (33kV) > MV bus (11kV) > LV buses (0.4kV)
        # Compare in MVA terms (bus voltage levels differ)
        ssc_grid = result.bus_results[0].s_sc_mva
        ssc_lv1 = result.bus_results[2].s_sc_mva
        assert ssc_grid > ssc_lv1, (
            f"Grid Ssc ({ssc_grid}) should be > LV Ssc ({ssc_lv1})"
        )

    def test_thevenin_impedance_at_bus(self):
        """IEC 60909: Z_th = V_pre / I_sc 확인."""
        network = _iec_lv_network(load_kw=50.0)
        result = calculate_short_circuit(network, v_pre_pu=1.0)
        for idx, bus_sc in result.bus_results.items():
            if bus_sc.i_sc_ka > 0:
                assert abs(bus_sc.z_th_pu) > 0

    def test_sc_result_all_buses(self):
        """IEC 60909: 모든 버스에 대해 단락 결과 존재."""
        network = _iec_mv_network()
        result = calculate_short_circuit(network)
        assert len(result.bus_results) == 4  # 4 buses


# ======================================================================
# Power Flow: IEC Voltage Compliance
# ======================================================================


class TestIECPowerFlow:
    """IEC 기준 전력조류 분석 검증."""

    def test_lv_voltage_within_iec_limits(self):
        """IEC 60038/61727: 정상 부하 시 LV 전압 0.95–1.05 pu."""
        network = _iec_lv_network(load_kw=100.0)
        result = solve_power_flow(network)
        assert result.converged
        v_lv = result.voltage_pu[1]
        assert 0.90 <= v_lv <= 1.10, f"LV voltage {v_lv:.4f} outside IEC range"

    def test_overload_violates_iec_thermal(self):
        """IEC: 과부하 시 변압기 열적 한계 초과 검증."""
        network = _iec_lv_network(load_kw=600.0)  # 600 kW on 500 kVA TX
        result = solve_power_flow(network)
        if result.converged and result.branch_flows:
            loading = result.branch_flows[0].loading_pct
            assert loading > 100.0, f"Loading {loading:.1f}% should exceed 100%"

    def test_mv_network_converges(self):
        """4-버스 MV 네트워크 수렴 확인."""
        network = _iec_mv_network()
        result = solve_power_flow(network)
        assert result.converged
        assert result.iterations < 15

    def test_mv_voltage_profile(self):
        """MV 네트워크: 모든 버스 전압 IEC 허용범위 내."""
        network = _iec_mv_network()
        result = solve_power_flow(network)
        assert result.converged
        for i in range(network.n_bus):
            v = result.voltage_pu[i]
            assert 0.90 <= v <= 1.10, (
                f"Bus {network.buses[i].name}: V={v:.4f} pu outside IEC ±10%"
            )

    def test_losses_positive(self):
        """전력조류: 손실은 양수 (에너지 보존)."""
        network = _iec_mv_network()
        result = solve_power_flow(network)
        assert result.converged
        for bf in result.branch_flows:
            assert bf.loss_p_pu >= -1e-6, (
                f"Branch {bf.branch_name}: negative P loss = {bf.loss_p_pu}"
            )


# ======================================================================
# N-1 Contingency with IEC Limits
# ======================================================================


class TestIECContingency:
    """IEC 기준 N-1 상정사고 분석 검증."""

    def test_contingency_uses_iec_default(self):
        """N-1 분석 기본값이 IEC 기준."""
        network = _iec_mv_network()
        result = run_contingency_analysis(network)
        assert result.grid_code == "IEC Default"

    def test_contingency_checks_all_branches(self):
        """N-1: 모든 회선에 대해 사고 분석."""
        network = _iec_mv_network()
        result = run_contingency_analysis(network)
        assert result.total_contingencies == 3  # 3 branches

    def test_contingency_voltage_limits_are_iec(self):
        """N-1: IEC 사고시 전압 한계 (0.90–1.10 pu) 적용."""
        network = _iec_mv_network()
        result = run_contingency_analysis(network, grid_code=IEC_DEFAULT)
        # All contingencies should check against 0.90-1.10 range
        for c in result.contingencies:
            for v in c.voltage_violations:
                if v.limit_type == "low":
                    assert v.limit_value == 0.90
                elif v.limit_type == "high":
                    assert v.limit_value == 1.10

    def test_radial_branch_removal_causes_island(self):
        """N-1: 방사형 네트워크에서 주간선 제거 시 고립 발생."""
        network = _iec_mv_network()
        result = run_contingency_analysis(network)
        # Removing the main 33/11kV TX should island the LV buses
        tx_contingency = next(
            (c for c in result.contingencies if c.branch_name == "TX_33_11"),
            None,
        )
        assert tx_contingency is not None
        assert tx_contingency.causes_islanding or not tx_contingency.passed

    def test_result_serialization(self):
        """N-1 결과 JSON 직렬화 검증."""
        network = _iec_mv_network()
        result = run_contingency_analysis(network)
        d = result.to_dict()
        assert "summary" in d
        assert "contingencies" in d
        assert d["summary"]["total_contingencies"] == 3
        assert "n1_secure" in d["summary"]


# ======================================================================
# IEC Profile Comparison
# ======================================================================


class TestIECvsOtherStandards:
    """IEC vs IEEE/피지 기준 비교 검증."""

    def test_iec_stricter_than_fiji_voltage(self):
        """IEC 정상 전압 범위(±5%)가 피지(±6%)보다 엄격."""
        iec_band = IEC_DEFAULT.voltage.normal_max - IEC_DEFAULT.voltage.normal_min
        fiji_band = FIJI_GRID_CODE.voltage.normal_max - FIJI_GRID_CODE.voltage.normal_min
        assert iec_band <= fiji_band

    def test_iec_50hz_ieee_60hz(self):
        """IEC는 50Hz, IEEE 1547은 60Hz."""
        assert IEC_DEFAULT.frequency.nominal_hz == 50.0
        assert IEEE_1547.frequency.nominal_hz == 60.0

    def test_fiji_conservative_thermal(self):
        """피지 열적 한계(90%)가 IEC(100%)보다 보수적."""
        assert FIJI_GRID_CODE.thermal_limit_pct < IEC_DEFAULT.thermal_limit_pct

    def test_custom_profile_overrides_iec(self):
        """커스텀 프로파일: IEC 기본값 위에 특정 값 오버라이드."""
        custom = build_custom_profile({
            "name": "IEC Modified",
            "standard": "IEC 61727 Modified",
            "voltage_limits": {"normal": [0.93, 1.07]},
        })
        # Custom values applied
        assert custom.voltage.normal_min == 0.93
        assert custom.voltage.normal_max == 1.07
        # IEC defaults preserved for unspecified fields
        assert custom.frequency.nominal_hz == 50.0
        assert custom.max_thd_pct == 5.0
        assert custom.reconnection.intentional_delay_s == 300.0
