# GridFlow - 종합 전력망 분석 웹서비스 브레인스토밍

## 1. 상용 툴 분석 및 GAP 식별

### 1.1 상용/오픈소스 툴 비교

| 툴 | 핵심 기능 | 지원 그리드 | 강점 | 약점 | 가격 |
|---|---|---|---|---|---|
| **HOMER Pro** | Microgrid 설계, Dispatch, 경제성 | Off-grid, Microgrid, Grid-tied | 사용 편의성, RE 최적화 | 상세 전기적 분석 불가 (Load Flow X, Harmonic X), 시간해상도 제한 | $5K-50K/yr |
| **PSS/E** | Load Flow, 안정도, 단락 | Transmission (유틸리티) | 업계 표준, 대규모 계통 | Distribution 미지원, 비싼, 폐쇄적 | $50K-200K+ |
| **ETAP** | Load Flow, 단락, 보호협조, 고조파 | Utility, Industrial | 가장 포괄적, 실시간 가능 | 매우 비싸, Desktop only | $20K-500K+ |
| **PowerWorld** | Load Flow, OPF, 시각화 | Transmission | 뛰어난 시각화 | Distribution 약함 | $5K-50K |
| **DIgSILENT** | Load Flow, RMS/EMT 시뮬레이션 | Transmission, Distribution | 풍력/태양광 모델 상세 | 학습곡선 높음, 비싼 | $15K-100K+ |
| **OpenDSS** | Distribution Load Flow, DER | Distribution, Microgrid | 무료, COM/Python API | UI 부족, 최적화 기능 없음 | 무료 |
| **PSCAD** | EMT 시뮬레이션 | 전체 (상세 과도현상) | 상세 과도현상 분석 | 느림, 대규모 계통 부적합 | $10K-80K |
| **GridLAB-D** | Distribution 시뮬레이션, 수요반응 | Distribution, Smart Grid | 무료, 시계열 강점 | 문서 부족, 학습곡선 | 무료 |
| **SAM (NREL)** | RE 성능, 경제성 | Grid-tied RE | 무료, 상세 RE 모델 | 전력계통 분석 없음 | 무료 |
| **Pandapower** | Load Flow, 단락, OPF | Transmission, Distribution | 무료, Python 네이티브 | 고조파X, 안정도X, UI 없음 | 무료 |
| **PyPSA** | OPF, 투자계획, Dispatch | Transmission, 국가규모 | 무료, 대규모 최적화 | 배전 약함, 실시간X | 무료 |
| **MATPOWER** | Load Flow, OPF | Transmission | 학술 표준, 검증됨 | MATLAB 필요, UI 없음 | MATLAB 라이선스 |

### 1.2 핵심 GAP (어떤 단일 툴도 커버하지 못하는 영역)

```
┌─────────────────────────────────────────────────────────────────┐
│                     현재 시장의 핵심 GAP (10가지)                  │
├─────────────────────────────────────────────────────────────────┤
│ 1. 통합 설계→운영 플랫폼 부재                                     │
│    HOMER(사이징) → ETAP(전기설계) → PSCAD(파워일렉) → 커스텀(운영) │
│    4개 도구를 순차적으로 사용해야 함                                 │
│                                                                 │
│ 2. 웹 기반 플랫폼 전무                                            │
│    모든 상용 툴이 Desktop 전용, 협업/클라우드 불가                   │
│                                                                 │
│ 3. 멀티타임스케일 시뮬레이션 불가                                   │
│    μs(EMT) → ms(과도안정도) → hr(디스패치) → yr(투자계획)           │
│    단일 프레임워크에서 통합 불가 (HELICS 코시뮬이 유일한 대안)        │
│                                                                 │
│ 4. 송배전 통합 최적화 부재                                        │
│    PyPSA(송전OPF) + OpenDSS(배전PF) + HOMER(DER경제성) 분리       │
│    T-D 통합 OPF + DER 투자최적화 오픈소스 전무                     │
│                                                                 │
│ 5. 현대적 그리드 토폴로지 미지원                                   │
│    VPP, P2P 에너지거래, 하이브리드 AC/DC 마이크로그리드              │
│    IEEE 2030.7 마이크로그리드 컨트롤러 시뮬레이션 부재               │
│                                                                 │
│ 6. 오픈소스 EMT 시뮬레이션 부재                                    │
│    PSCAD가 골드 스탠다드이나 고가, 오픈소스 대안 미성숙               │
│                                                                 │
│ 7. 섹터 커플링 + 전기적 상세 분석 동시 불가                         │
│    PyPSA(전력-가스-열 연계) vs PowerFactory(전기분석)               │
│    둘 다 동시에 제공하는 도구 없음                                   │
│                                                                 │
│ 8. 확률론적 분석의 부재                                            │
│    대부분 결정론적. Stochastic OPF, 확률론적 PF 네이티브 지원 없음    │
│                                                                 │
│ 9. 표준 데이터 교환 포맷 분열                                      │
│    CIM(IEC 61970) 표준 존재하나, 도구간 모델 변환 여전히 고통        │
│                                                                 │
│ 10. IBR(인버터 기반 자원) + 대규모 계통 동시 분석 불가               │
│     PSCAD(상세 인버터) ↔ PSS/E(대규모 계통) 사이 격차               │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 상세 기능 비교 매트릭스

| 기능 | HOMER | PSS/E | ETAP | PowerFactory | OpenDSS | Pandapower | PyPSA | MATPOWER |
|---|---|---|---|---|---|---|---|---|
| AC Power Flow | X | O | O | O | O | O | O | O |
| 3-Phase 불평형 | X | X | O | O | O | 부분 | X | X |
| OPF | X | O | O | O | X | O | O | O |
| Unit Commitment | X | X | X | X | X | X | O | O(MOST) |
| 과도안정도 | X | O | O | O | X | X | X | X |
| EMT 시뮬레이션 | X | X | X | O | X | X | X | X |
| 고조파분석 | X | X | O | O | O | X | X | X |
| 단락해석 | X | O | O | O | O | O | X | X |
| 마이크로그리드 Dispatch | O | X | O | 부분 | X | X | 부분 | X |
| 경제성분석 | O | X | X | X | X | X | O | X |
| RE 성능모델 | 간이 | X | X | 부분 | 부분 | X | X | X |
| 용량 확장 계획 | X | X | X | X | X | X | O | X |
| Python API | X | O | 제한 | O | O | 네이티브 | 네이티브 | X(MATLAB) |
| 오픈소스 | X | X | X | X | O | O | O | O |
| 데이터센터 특화 | X | X | 부분 | X | X | X | X | X |
| PUE/신뢰도 분석 | X | X | X | X | X | X | X | X |
| **웹 기반** | **X** | **X** | **X** | **X** | **X** | **X** | **X** | **X** |

---

## 2. GridFlow 포지셔닝 전략

### 2.1 핵심 차별화 컨셉

```
GridFlow = HOMER의 사용성 + PSS/E의 정밀도 + 웹 기반 접근성
```

**타겟 사용자:**
1. **Tier 1**: 마이크로그리드/Off-grid 설계 엔지니어 (HOMER 대체)
2. **Tier 2**: 배전계통 엔지니어 (OpenDSS + ETAP 부분 대체)
3. **Tier 3**: 에너지 컨설턴트, 연구자
4. **Tier 4**: 유틸리티 기획 엔지니어

### 2.2 제품 비전

```
┌──────────────────────────────────────────────────────────────┐
│                    GridFlow 기능 레이어                        │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Layer 4: 의사결정 지원                       │ │
│  │  경제성분석(LCOE/NPC) │ 민감도분석 │ 시나리오비교 │ 보고서   │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Layer 3: 최적화 엔진                        │ │
│  │  Optimal Sizing │ Dispatch(LP/MILP) │ OPF │ 투자 최적화  │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Layer 2: 전력계통 분석                       │ │
│  │  Load Flow(NR/FDLF/FBS) │ Harmonic │ 단락 │ 안정도       │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Layer 1.5: 데이터센터 특화                    │ │
│  │  UPS 모델 │ PDU │ IT부하(CPU/GPU) │ 냉각(COP) │ 신뢰도   │ │
│  │  PUE분석 │ ITIC곡선 │ Tier분류 │ DC배전 │ Arc Flash     │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Layer 1: 에너지 자원 모델링                   │ │
│  │  Solar PV │ Wind │ Battery │ Diesel │ Fuel Cell │ Hydro  │ │
│  │  Grid │ Load │ EV │ Electrolyzer │ H2 Storage │ SMR     │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Layer 0: 데이터 & 인프라                     │ │
│  │  기상데이터(TMY/실시간) │ 부하프로파일 │ 장비DB │ 요금체계   │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. 핵심 분석 엔진 설계

### 3.1 Load Flow 엔진

| 방법 | 용도 | 정확도 | 속도 | 구현 우선순위 |
|---|---|---|---|---|
| **Newton-Raphson (NR)** | 범용 Load Flow | 높음 | 중간 | **P0 (핵심)** |
| **Fast Decoupled (FDLF)** | 대규모 송전 | 높음 | 빠름 | P1 |
| **DC Power Flow** | 초기 추정, OPF | 근사 | 매우 빠름 | P1 |
| **Forward-Backward Sweep** | 방사형 배전 | 높음 | 매우 빠름 | **P0 (핵심)** |
| **3-phase Unbalanced NR** | 불평형 배전 | 매우 높음 | 느림 | P2 |
| **Continuation PF** | 전압안정도 | 높음 | 느림 | P2 |

**Newton-Raphson 핵심 수식:**
```
[ΔP]   [H  N] [Δθ]
[  ] = [    ] [  ]
[ΔQ]   [M  L] [ΔV/V]

여기서 Jacobian 부분행렬:
H_ij = ∂P_i/∂θ_j,  N_ij = V_j·∂P_i/∂V_j
M_ij = ∂Q_i/∂θ_j,  L_ij = V_j·∂Q_i/∂V_j
```

### 3.2 Dispatch 엔진

**HOMER와 동등 + 확장:**
```
Minimize: Σ_t [ Σ_g C_fuel(P_g,t) + C_OM + C_degradation(Battery) ]

Subject to:
  Σ_g P_g,t + P_PV,t + P_Wind,t + P_Batt_discharge,t = P_Load,t + P_Batt_charge,t + P_dump,t
  P_g,min ≤ P_g,t ≤ P_g,max                    (발전기 출력 제약)
  SOC_min ≤ SOC_t ≤ SOC_max                      (배터리 SOC 제약)
  SOC_t = SOC_{t-1} + η_c·P_charge·Δt/E_batt - P_discharge·Δt/(η_d·E_batt)
  u_g,t ∈ {0,1}  (발전기 ON/OFF - MILP)
  P_g,t ≤ u_g,t · P_g,max
  P_g,t ≥ u_g,t · P_g,min
```

### 3.3 Harmonic 분석 엔진

```
각 고조파 h에 대해:
Y_bus(h) = 재구성 (주파수 의존 임피던스)
I_h = 주입 고조파 전류 벡터
V_h = Y_bus(h)^{-1} · I_h

THD_V = √(Σ_{h=2}^{H_max} V_h²) / V_1 × 100%
TDD_I = √(Σ_{h=2}^{H_max} I_h²) / I_L × 100%  (I_L: 최대수요전류)
```

### 3.4 RE 자원 모델링

**Solar PV (Single-Diode Model):**
```
I = I_ph - I_0·[exp((V + I·Rs)/(n·Vt)) - 1] - (V + I·Rs)/Rp

여기서:
I_ph = (I_ph_STC + Ki·(T - 25)) · G/1000     (광전류)
I_0 = I_0_STC · (T/T_STC)³ · exp(Eg/(n·k)·(1/T_STC - 1/T))  (역포화전류)
Vt = k·T/q                                     (열전압)
```

**Battery (KiBaM + Degradation):**
```
dq1/dt = -I + k·(q2/c2 - q1/c1)    (가용 충전량)
dq2/dt = k·(q1/c1 - q2/c2)          (결합 충전량)

열화: Q_remaining = Q_initial × (1 - L_cycle - L_calendar)
```

---

## 4. 기술 스택 제안

### 4.1 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│  React/Next.js + TypeScript                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ 단선도    │ │ 시계열   │ │ 결과     │ │ 지도     │       │
│  │ Editor   │ │ Charts   │ │ Tables   │ │ (위치)   │       │
│  │(Canvas/  │ │(D3/      │ │(AG-Grid) │ │(Mapbox)  │       │
│  │ SVG)     │ │ Plotly)  │ │          │ │          │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST/WebSocket/GraphQL
┌──────────────────────────┴──────────────────────────────────┐
│                      Backend (API)                            │
│  Python (FastAPI) + Celery (비동기 작업)                       │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              Analysis Engine (Python/C)               │    │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐        │    │
│  │  │LoadFlow│ │Dispatch│ │Harmonic│ │ShortCkt│        │    │
│  │  │(NumPy/ │ │(HiGHS/ │ │(NumPy/ │ │(NumPy/ │        │    │
│  │  │SciPy)  │ │Pyomo)  │ │SciPy)  │ │SciPy)  │        │    │
│  │  └────────┘ └────────┘ └────────┘ └────────┘        │    │
│  │  ┌────────┐ ┌────────┐ ┌────────┐                    │    │
│  │  │Solar PV│ │Wind    │ │Battery │                    │    │
│  │  │Model   │ │Model   │ │Model   │                    │    │
│  │  └────────┘ └────────┘ └────────┘                    │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                      Data Layer                               │
│  PostgreSQL (프로젝트/사용자) + TimescaleDB (시계열)            │
│  Redis (캐시/세션) + S3 (파일/보고서)                           │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 기술 스택 선정 근거

| 영역 | 기술 | 근거 |
|---|---|---|
| **Frontend** | Next.js + TypeScript | SSR, 라우팅, 타입 안전성 |
| **단선도 Editor** | React Flow / Canvas API | 전력계통 SLD 드래그앤드롭 |
| **차트** | Plotly.js / D3.js | 시계열 (8760시간), 인터랙티브 |
| **Backend API** | FastAPI (Python) | 비동기, 자동 문서, 타입 힌트 |
| **분석 엔진** | NumPy/SciPy + C/Rust 확장 | 행렬 연산, 희소행렬, 성능 |
| **최적화 솔버** | HiGHS (LP/MILP) + IPOPT (NLP) | 오픈소스, 성능 검증됨 |
| **최적화 모델링** | Pyomo | 유연한 모델 정의, 복수 솔버 지원 |
| **비동기 작업** | Celery + Redis | 장시간 시뮬레이션 처리 |
| **DB** | PostgreSQL + TimescaleDB | 관계형 + 시계열 최적화 |
| **인증** | Auth0 / Supabase Auth | OAuth2, 멀티테넌트 |
| **배포** | Docker + K8s (AWS/GCP) | 확장성, 격리 |

### 4.3 핵심 솔버 엔진 - Python vs C/Rust 결정

```
Phase 1 (MVP): 순수 Python (NumPy/SciPy)
  - 빠른 개발, 검증 용이
  - 1000-bus 이하 충분한 성능
  - scipy.sparse 활용으로 Y_bus 효율적 처리

Phase 2 (성능): C/Rust 확장 모듈
  - NR 반복 루프, Jacobian 계산을 C로
  - PyBind11 또는 Rust(PyO3)로 Python 바인딩
  - 10,000+ bus 대응

대안: pandapower의 내부 엔진 활용 검토
  - pandapower는 Newton-Raphson을 이미 구현
  - 라이브러리로 활용 가능 (BSD 라이선스)
  - 단, 커스터마이징 한계 있음
```

---

## 5. 개발 로드맵 (단계별)

### Phase 0: Foundation (4-6주)
```
목표: 프로젝트 구조, CI/CD, 핵심 데이터 모델
├── 모노레포 구조 설정 (pnpm workspace 또는 nx)
├── Backend: FastAPI 기본 구조 + DB 스키마
├── Frontend: Next.js 기본 구조 + 인증
├── 핵심 데이터 모델 (Bus, Branch, Generator, Load, DER)
├── 단위 테스트 프레임워크
└── Docker Compose 개발환경
```

### Phase 1: Core Engine - "HOMER Killer" (8-12주)
```
목표: Microgrid/Off-grid 시스템 설계 & 시뮬레이션
├── Energy Resource Models
│   ├── Solar PV (Single-diode, Perez irradiance)
│   ├── Wind Turbine (Power curve, Weibull)
│   ├── Battery (KiBaM, Coulomb counting, 기본 열화)
│   ├── Diesel Generator (연료 곡선, 최소 부하)
│   └── Grid Connection (요금 스케줄)
├── Dispatch Engine
│   ├── Rule-based dispatch (Cycle Charging, Load Following)
│   ├── LP-based optimal dispatch
│   └── Multi-period with battery SOC tracking
├── Load Flow (기본)
│   ├── Newton-Raphson (balanced, single-phase equivalent)
│   └── 버스 전압/조류 계산
├── Economic Analysis
│   ├── NPC (Net Present Cost)
│   ├── LCOE (Levelized Cost of Energy)
│   ├── IRR, Payback Period
│   └── 민감도 분석
├── Frontend
│   ├── 시스템 구성 UI (컴포넌트 드래그앤드롭)
│   ├── 시계열 결과 차트 (8760h)
│   ├── 경제성 결과 대시보드
│   └── 프로젝트 저장/불러오기
└── Weather/Resource Data
    ├── TMY 데이터 통합 (PVGIS, NSRDB API)
    └── 부하 프로파일 라이브러리
```

### Phase 2: Power System Analysis (8-12주)
```
목표: 전기적 분석 역량 추가 (ETAP 영역 진입)
├── Load Flow 확장
│   ├── Fast Decoupled Load Flow
│   ├── DC Power Flow
│   ├── Forward-Backward Sweep (방사형)
│   └── PV/PQ 버스 전환, 탭 변압기
├── Short Circuit Analysis
│   ├── IEC 60909 방법
│   ├── 대칭좌표법 (정상/역상/영상)
│   ├── 3상, 1선지락, 선간, 2선지락 고장
│   └── 차단기 용량 검증
├── Harmonic Analysis
│   ├── 주파수별 Y_bus 구성
│   ├── 고조파 전류 주입법
│   ├── THD/TDD 계산
│   ├── IEEE 519 적합성 판정
│   └── 인버터/비선형부하 고조파 모델
├── Frontend
│   ├── 단선도(SLD) 에디터
│   ├── 결과 시각화 (전압 프로파일, 조류도)
│   └── 보고서 생성 (PDF)
└── 검증
    ├── IEEE 테스트 시스템 (9-bus, 14-bus, 30-bus, 118-bus)
    ├── pandapower/MATPOWER 결과 대조
    └── 실측 데이터 비교
```

### Phase 3: Advanced Features (12-16주)
```
목표: 차세대 그리드 분석
├── Optimal Power Flow (OPF)
│   ├── DC-OPF (LP)
│   ├── AC-OPF (NLP, IPOPT)
│   └── Security-Constrained OPF
├── Unit Commitment (MILP)
├── Stability Analysis (기본)
│   ├── 전압 안정도 지표 (L-index)
│   ├── P-V / Q-V 곡선
│   └── 주파수 응답 (집합 모델)
├── Microgrid 고급
│   ├── AC/DC 하이브리드 마이크로그리드
│   ├── Droop 제어 모델링
│   ├── Islanding 전환 시뮬레이션
│   └── 멀티 마이크로그리드
├── VPP & P2P
│   ├── DER 집합 모델
│   ├── P2P 거래 시뮬레이션
│   └── Prosumer 모델
├── 추가 자원 모델
│   ├── Fuel Cell (분극 곡선)
│   ├── Electrolyzer (P2G)
│   ├── Small Hydro
│   ├── EV Charging (V2G 포함)
│   └── Thermal Storage (CHP)
└── API & 연동
    ├── REST API (외부 연동)
    ├── Python SDK
    └── IEC 61850 데이터 모델 매핑
```

---

## 6. 핵심 기술적 결정 사항

### 6.1 검증 전략 (과학적 신뢰성 확보)

```
1. IEEE 표준 테스트 시스템으로 검증
   - IEEE 9-bus, 14-bus, 30-bus, 57-bus, 118-bus, 300-bus
   - 결과를 MATPOWER/pandapower와 비교 (수치 오차 < 1e-6)

2. 학술 논문 기반 알고리즘
   - 모든 솔버는 교과서/논문의 수식을 직접 구현
   - 참고: Glover "Power Systems Analysis & Design"
   - 참고: Saadat "Power System Analysis"
   - 참고: Bergen & Vittal "Power Systems Analysis"

3. 상용 소프트웨어 결과 교차검증
   - HOMER Pro 결과와 dispatch 비교
   - ETAP/pandapower와 Load Flow 비교

4. 실측 데이터 검증
   - 실제 마이크로그리드 운영 데이터와 시뮬레이션 비교
   - NREL/DOE 공개 데이터셋 활용
```

### 6.2 성능 목표

```
Load Flow (NR):
  - 100 bus: < 0.1초
  - 1,000 bus: < 1초
  - 10,000 bus: < 10초 (Phase 2, C 확장)

Dispatch (8760시간):
  - Rule-based: < 2초
  - LP-based: < 10초
  - MILP (with UC): < 60초

Harmonic (50차까지):
  - 100 bus: < 5초
```

### 6.3 수학적 기반 요약

```
┌─────────────────────────────────────────────────────────────┐
│                   수학적 기반 (검증된 이론)                     │
├──────────────┬──────────────────────────────────────────────┤
│ Load Flow    │ Newton-Raphson with Jacobian                 │
│              │ Y_bus = G + jB (admittance matrix)           │
│              │ P + jQ = V · (Y_bus · V)*                    │
├──────────────┼──────────────────────────────────────────────┤
│ Short Circuit│ IEC 60909, 대칭좌표법                         │
│              │ I"k = c·Vn / (√3·|Z₁|)                      │
├──────────────┼──────────────────────────────────────────────┤
│ Harmonics    │ Fourier Analysis, IEEE 519                   │
│              │ THD = √(ΣVh²)/V₁ × 100%                     │
├──────────────┼──────────────────────────────────────────────┤
│ OPF          │ min f(x) s.t. g(x)=0, h(x)≤0              │
│              │ KKT conditions, Interior Point Method        │
├──────────────┼──────────────────────────────────────────────┤
│ Dispatch     │ LP/MILP (HiGHS), Energy Balance              │
│              │ Σ P_gen = Σ P_load (매 시간)                  │
├──────────────┼──────────────────────────────────────────────┤
│ Solar PV     │ Single-Diode Model (5-parameter)             │
│              │ I = Iph - I0·[exp((V+I·Rs)/(n·Vt))-1]       │
├──────────────┼──────────────────────────────────────────────┤
│ Wind         │ Power Curve + Weibull Distribution            │
│              │ P = 0.5·ρ·A·v³·Cp(λ,β)                      │
├──────────────┼──────────────────────────────────────────────┤
│ Battery      │ KiBaM + ECM + Degradation                    │
│              │ SOC tracking, Calendar + Cycle aging          │
├──────────────┼──────────────────────────────────────────────┤
│ Stability    │ Swing Equation: 2H/ωs · d²δ/dt² = Pm - Pe   │
│              │ Small-signal: eigenvalue of state matrix      │
└──────────────┴──────────────────────────────────────────────┘
```

---

## 7. 경쟁 우위 & 비즈니스 모델

### 7.1 경쟁 우위

| 기존 도구 한계 | GridFlow 해결책 |
|---|---|
| Desktop 전용 | **웹 기반** - 브라우저에서 즉시 사용 |
| 고가 라이선스 ($5K-500K) | **SaaS** - 월 구독, 무료 Tier 제공 |
| 분석별 별도 소프트웨어 | **통합 플랫폼** - 하나에서 모든 분석 |
| 협업 불가 | **실시간 협업** - 프로젝트 공유 |
| API/자동화 부재 | **API-first** - 자동화, CI/CD 연동 |
| 검증 불투명 | **오픈 알고리즘** - 수식/소스 공개 가능 |

### 7.2 비즈니스 모델

```
Free Tier:     단일 프로젝트, 10-bus 이하, 기본 분석
Professional:  $49/월 - 무제한 프로젝트, 1000-bus, 전체 분석
Enterprise:    $199/월 - 팀 협업, API, 고급 최적화, 대규모 계통
On-Premise:    별도 견적 - 자체 서버 설치, 커스터마이징
```

---

## 8. 데이터센터 전력 분석 특화 모듈

### 8.1 시장 배경 - 왜 데이터센터인가?

```
┌─────────────────────────────────────────────────────────────────┐
│                  데이터센터 전력 수요 폭증                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  글로벌 데이터센터 전력 소비:                                      │
│    2024: ~415 TWh (~55 GW)     │ 전체 전력의 ~1.5%               │
│    2026: ~650-1,050 TWh (IEA)  │ AI 수요 90% 차지               │
│    2030: ~945 TWh (~200 GW)    │ 전체 전력의 ~3.0%               │
│                                                                 │
│  AI/GPU 워크로드가 핵심 드라이버:                                   │
│    - GPU 서버 랙: 132 kW/rack (차세대 240 kW/rack)               │
│    - AI 전력 수요: 2026년 ~40 GW (전체의 42%)                     │
│    - 빅테크 2026년 AI 인프라 투자: $600B+                         │
│                                                                 │
│  그리드 스트레스 포인트:                                           │
│    - 북버지니아: 2,078 MW 건설중, 인터커넥션 대기 ~7년              │
│    - 텍사스(ERCOT): 대규모 부하 신청 700% 증가 (1→8 GW)            │
│    - 단일 캠퍼스 1-3 GW급 신규 건설 (소도시 전체 전력 규모)          │
│                                                                 │
│  ★ 기존 분석 도구 중 데이터센터 특화 도구 = 0개                     │
│    ETAP: 산업시설 범용 (DC 특화 X)                                │
│    HOMER: 전기적 분석 없음                                        │
│    CFD: 열분석만 (전기분석 X)                                     │
│    → 4-6개 도구를 조합해야 하는 상황                               │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 데이터센터 전력 아키텍처

```
                    Utility Feed A ──┐              ┌── Utility Feed B
                                     │              │
                               ┌─────▼─────┐  ┌────▼──────┐
                               │ HV/MV Sub A│  │ HV/MV Sub B│
                               └─────┬─────┘  └────┬──────┘
                                     │              │
                               ┌─────▼─────┐  ┌────▼──────┐
                               │  ATS/STS   │  │  ATS/STS   │
                               └─────┬─────┘  └────┬──────┘
                                     │              │
                          ┌──────────▼────┐  ┌─────▼─────────┐
                          │  Generator A  │  │  Generator B   │
                          └──────┬────────┘  └──────┬────────┘
                                 │                   │
                          ┌──────▼────────┐  ┌──────▼────────┐
                          │  UPS A        │  │  UPS B         │
                          │  Rect→Batt→Inv│  │  Rect→Batt→Inv │
                          └──────┬────────┘  └──────┬────────┘
                                 │                   │
                          ┌──────▼────────┐  ┌──────▼────────┐
                          │  PDU A        │  │  PDU B         │
                          │  480V→208/120V│  │  480V→208/120V │
                          └──────┬────────┘  └──────┬────────┘
                                 │                   │
                                 └──────────┬────────┘
                                       ┌────▼─────┐
                                       │  Rack    │
                                       │ Dual PSU │
                                       └──────────┘

  Tier I  (99.671%): N 구성, 단일 경로
  Tier II (99.741%): N+1 구성, 단일 경로
  Tier III(99.982%): N+1 컴포넌트, 2N 분배, 동시 보수 가능
  Tier IV (99.995%): 2(N+1) 구성, 완전 내결함
```

### 8.3 데이터센터 특화 분석 영역

#### A. PUE (Power Usage Effectiveness) 분석

```
PUE = Total Facility Power / IT Equipment Power

PUE = 1 + (P_cooling/P_IT) + (P_UPS_loss/P_IT) + (P_PDU_loss/P_IT) + (P_misc/P_IT)

구성요소별 모델:
  P_cooling = P_CRAC + P_chiller + P_pump + P_tower + P_CDU(액체냉각)
  P_UPS_loss = P_IT × (1/η_UPS(load%) - 1)
  P_PDU_loss = P_IT × (1/η_PDU - 1)

UPS 효율 모델:
  η_UPS(P_load) = P_load / (P_load + P_no_load + k × P_load²)

  25% 부하: 88-93%  |  50%: 92-95%  |  75%: 93-96%  |  100%: 93-97%

냉각 COP 모델 (DOE-2):
  COP = COP_ref × f_temp(T_outdoor) × f_PLR(부분부하비)

업계 PUE 벤치마크:
  글로벌 평균: 1.58  |  Google: 1.09  |  최적화: 1.03-1.10
```

#### B. IT 부하 프로파일링 (GPU/CPU 구분)

| 특성 | 전통 CPU 서버 | GPU 학습 클러스터 | GPU 추론 서버 |
|---|---|---|---|
| 랙 전력 | 5-15 kW | 60-240 kW | 20-60 kW |
| 부하율 | 30-60% 평균 | 80-95% 지속 | 40-80% 주야변동 |
| 전력 램프 | 완만 | 급격 (초단위) | 중간 |
| 역률 | 0.95-0.99 | 0.90-0.98 | 0.92-0.98 |

```
GPU 학습 부하 모델:
  P(t) = P_idle + (P_max - P_idle) × job_active(t)
  job_active ∈ {0,1} - 학습 작업 시작시 수초내 0→100MW 스텝 부하

GPU 추론 부하 모델:
  P(t) = P_idle + (P_max - P_idle) × sigmoid(request_rate(t))
  주야 패턴 + 랜덤 변동
```

#### C. 신뢰도 분석

```
2N 시스템 Markov 모델:
  상태 0: 양쪽 정상   상태 1: A 고장, B 정상
  상태 2: B 고장, A 정상   상태 3: 양쪽 고장 (시스템 실패)

  가용도: A = 1 - (λ/(λ+μ))²

  여기서 λ = 고장률, μ = 수리율

Fault Tree Analysis:
  Top Event: IT 랙 전력 완전 차단
  = (Path A 고장) AND (Path B 고장)     [2N 구성]
  Path A 고장 = (유틸리티A 고장 AND 발전기A 고장) OR ATS_A 고장 OR UPS_A 고장

Monte Carlo 시뮬레이션:
  N회 반복:
    - 각 컴포넌트 고장시간 생성 (지수분포)
    - 수리시간 생성
    - 시스템 가동시간/정지시간 기록
  → MTBF, 가용도, 다운타임 분포 산출
```

#### D. 데이터센터 + 재생에너지 통합

```
24/7 Carbon-Free Energy (CFE) Score:
  CFE = Σ_t min(P_CFE(t), P_load(t)) / Σ_t P_load(t)

  목표: CFE = 100% (매 시간 탄소무배출 에너지로 매칭)

UPS 배터리의 그리드 서비스 이중활용:
  P_grid_service = P_UPS_rated - P_IT_load - P_reserve

  제약: SOC(t) ≥ SOC_min_backup (항상 IT 백업 시간 확보)
  SOC_min_backup = P_IT × T_backup_min / (E_battery × η_inv)

  수익: Revenue = Σ_t P_dispatched(t) × Price_regulation(t)

SMR (소형 모듈 원자로) 통합:
  - Microsoft: TMI 재가동 835MW ($16B, 2028 목표)
  - Amazon: 워싱턴주 12기 SMR (960MW)
  - Google: Kairos Power (500MW, 2030+)
  - 빅테크 합계 10GW+ 원자력 계약
```

#### E. DC 배전 분석 (380V/800V DC)

```
기존 AC 경로 효율:
  유틸리티AC → UPS(AC-DC-AC) → PDU변압기 → 서버PSU(AC-DC)
  손실: ~5%        ~3%         ~5-10%
  전체 효율: ~83-88%

380V DC 경로 효율:
  유틸리티AC → 정류기(AC-DC) → 배터리 → 서버PSU(DC-DC)
  손실: ~3%                          ~3%
  전체 효율: ~94-97%

800V DC 경로 (AI용):
  140kW/rack: 400VDC → 350A (500MCM 케이블)
              800VDC → 175A (3/0 AWG) → 케이블 비용 3배 절감
```

### 8.4 GridFlow 데이터센터 모듈 로드맵

```
Phase 1 추가 (MVP와 함께):
  ├── IT 부하 프로파일 (CPU/GPU 학습/GPU 추론)
  ├── UPS 효율 곡선 모델
  ├── 냉각 시스템 COP 모델
  ├── PUE 계산 엔진
  └── 재생에너지+배터리+UPS 통합 디스패치

Phase 2 추가 (전력분석과 함께):
  ├── 데이터센터 SLD 템플릿 (2N, N+1 등)
  ├── UPS 단락 기여 모델링
  ├── SMPS 집합 고조파 모델
  ├── ITIC/CBEMA 곡선 적합성
  ├── Arc Flash 분석 (IEEE 1584)
  └── 하이브리드 AC/DC 조류계산

Phase 3 추가 (고급기능과 함께):
  ├── 신뢰도 분석 (Markov, FTA, Monte Carlo)
  ├── 열-전기 결합 시뮬레이션
  ├── 24/7 CFE 최적화
  ├── UPS 그리드 서비스 이중활용 최적화
  ├── 워크로드 배치 최적화 (멀티사이트)
  └── TCO (Total Cost of Ownership) 분석
```

---

## 9. 확정된 개발 전략

### ✅ 3단계 개발 전략 (확정)

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  Phase 1: HOMER 대체 (MVP)                                      │
│  ─────────────────────────────────────────────────              │
│  목표: 마이크로그리드/Off-grid 시스템 설계 & 최적화                 │
│  핵심: Dispatch + RE 자원 모델 + 경제성 분석                       │
│  경쟁: HOMER Pro ($5K-50K/yr) 대체                               │
│  ┌───────────────────────────────────────────────┐              │
│  │ Solar PV (Single-diode) │ Wind (Power curve)  │              │
│  │ Battery (KiBaM+열화)    │ Diesel (연료곡선)     │              │
│  │ Grid Connection         │ Load Profile         │              │
│  │ Dispatch (LP/Rule)      │ NPC/LCOE/IRR         │              │
│  │ 시계열 시뮬레이션(8760h) │ 민감도 분석           │              │
│  └───────────────────────────────────────────────┘              │
│                                                                 │
│  Phase 2: 전력계통 분석 엔진                                      │
│  ─────────────────────────────────────────────────              │
│  목표: 전기적 분석 역량 완비 (ETAP/PSS/E 영역 진입)                │
│  핵심: Load Flow + Harmonic + 단락 + OPF + 안정도                 │
│  ┌───────────────────────────────────────────────┐              │
│  │ Newton-Raphson Load Flow │ FDLF │ DC PF       │              │
│  │ Forward-Backward Sweep   │ 3-Phase Unbalanced  │              │
│  │ Harmonic Analysis        │ IEEE 519 검증        │              │
│  │ Short Circuit (IEC60909) │ 대칭좌표법           │              │
│  │ AC/DC OPF (IPOPT/HiGHS) │ Unit Commitment      │              │
│  │ 전압안정도 (CPF, L-index)│ 주파수 응답 모델      │              │
│  │ SLD 에디터 (React Flow)  │ 보고서 생성 (PDF)     │              │
│  │ Fuel Cell │ Hydro │ EV  │ VPP │ P2P 거래       │              │
│  └───────────────────────────────────────────────┘              │
│                                                                 │
│  Phase 3: 데이터센터 특화 모듈                                    │
│  ─────────────────────────────────────────────────              │
│  목표: 데이터센터 전력 분석의 유일한 통합 플랫폼                     │
│  핵심: PUE + 신뢰도 + DC배전 + UPS 이중활용 + 24/7 CFE            │
│  ┌───────────────────────────────────────────────┐              │
│  │ IT 부하 모델 (CPU/GPU)  │ UPS 효율/단락 모델    │              │
│  │ 냉각 COP 모델           │ PUE 실시간 분석       │              │
│  │ Tier I-IV 신뢰도        │ Markov/FTA/Monte Carlo│              │
│  │ 380V/800V DC 배전       │ Arc Flash (IEEE 1584) │              │
│  │ ITIC/CBEMA 적합성       │ SMPS 집합 고조파      │              │
│  │ 24/7 CFE 최적화         │ UPS 그리드 서비스      │              │
│  │ 열-전기 결합 시뮬레이션   │ 워크로드 배치 최적화   │              │
│  │ TCO 분석                │ SMR 통합 모델         │              │
│  └───────────────────────────────────────────────┘              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### ✅ 기타 결정 사항 (미결 - 구현 시 결정)
- 오픈소스 전략: 코어 엔진 오픈소스 + 웹서비스 상용 (권장)
- SLD 에디터: React Flow 기반 (Phase 2에서 구현)
- 솔버 성능: Phase 1은 순수 Python, Phase 2부터 C/Rust 확장 검토
