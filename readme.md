# Projekt: Analiza Rynków Polymarket z Wykorzystaniem ML

Projekt zakłada wykorzystanie danych z Polymarket (Gamma API) do analizy zachowania rynków predykcyjnych oraz budowy modeli uczenia maszynowego przewidujących poziom zaangażowania użytkowników. Dane będą zbierane cyklicznie przez endpoint `/events`, a rynki zapisywane w postaci statycznego opisu i historii snapshotów w katalogu `data/`.

---

## Cel projektu

- Zbudowanie własnego „mini data lake” z rynków Polymarket na potrzeby analiz ML.
- Przeprowadzenie **3 analiz ML (np. klasyfikacja, regresja, klasteryzacja – dokładny wybór po wstępnej EDA).
- Zbadanie, jakie cechy rynku (volume, liquidity, price, kategoria, czas do końca) najlepiej tłumaczą wysokie zaangażowanie użytkowników (wysokie obroty, płynność, aktywność).

Projekt koncentruje się na praktycznym pipeline:
**pobieranie danych → czyszczenie → budowa cech → modele → wnioski.**

---

## Dane wejściowe

### Źródło danych

- **Polymarket Gamma API** – w szczególności endpoint:
  - `GET /events` – lista eventów wraz z osadzonymi rynkami (`markets`), z możliwością filtrowania po `active`/`closed` i sortowania po `id`.

### Zakres zbieranych informacji

Z odpowiedzi `/events` (pole `markets` przy każdym evencie) planowane jest zbieranie:

- **Opis rynku (meta, raczej stałe):**
  - `m.id` → `market_id` – główny identyfikator rynku.
  - `ev.id` → `event_id` – identyfikator eventu.
  - `ev.slug` → `event_slug`.
  - `ev.title` → `event_title`.
  - `m.slug` → `market_slug`.
  - `m.question` / `m.title` → `question`.
  - `ev.category`, `ev.subcategory` (fallback: `m.category`) → `category`, `subcategory`.
  - `m.createdAt` → `created_at`.
  - `m.endDate` / `m.umaEndDate` → `end_date`.
  - `m.resolutionSource` → `resolution_source`.

- **Stan i zaangażowanie (zmienne w czasie, snapshoty):**
  - `m.active`, `m.closed`, `m.featured`, `m.new` – statusy rynku.
  - `m.volume24hr`, `m.volume24hrNum` – `volume24hr` (obrót 24h).
  - `m.volume1wk` → `volume1wk`.
  - `m.volume1mo` → `volume1mo`.
  - `m.volume1yr` → `volume1yr`.
  - `m.volume`, `m.volumeNum` → `volume_total`.
  - `m.liquidity`, `m.liquidityNum` → `liquidity`.
  - `m.liquidityAmm`, `m.liquidityClob` → `liquidityAmm`, `liquidityClob`.
  - `m.openInterest` → `openInterest`.
  - `m.lastTradePrice` → `lastTradePrice`.
  - `m.bestBid`, `m.bestAsk`, `m.spread` → `bestBid`, `bestAsk`, `spread`.
  - `m.oneDayPriceChange`, `m.oneWeekPriceChange` → `oneDayPriceChange`, `oneWeekPriceChange`.
  - `m.commentCount` → `commentCount`.
  - `m.competitive` → `competitive`.
  - `m.score` → `score`.

Dodatkowo każdy snapshot dostaje własny timestamp pobrania po stronie klienta:
- `snapshot_ts = datetime.now(timezone.utc).isoformat()`.

---

## Format i struktura danych (katalog `data/`)

Dane z API są zapisywane w dwóch plikach CSV, w katalogu `data/`:

### 1. `data/markets_static.csv`

Opisuje **tożsamość i kontekst** rynku. Jeden wiersz na `market_id`.

Kolumny (STATIC_FIELDS):

- `market_id` – identyfikator rynku (klucz główny).
- `event_id` – identyfikator eventu.
- `event_slug` – slug eventu.
- `event_title` – tytuł eventu.
- `market_slug` – slug rynku.
- `question` – tekst pytania/rynku.
- `category` – kategoria główna (np. Politics, Sports).
- `subcategory` – podkategoria (jeśli dostępna).
- `created_at` – czas utworzenia rynku.
- `end_date` – planowana data końca rynku.
- `resolution_source` – źródło rozstrzygnięcia rynku.

Te dane zmieniają się rzadko lub wcale, więc nie muszą być powielane w każdej obserwacji czasowej.

### 2. `data/markets_snapshots.csv`

Opisuje **stan rynku w konkretnym momencie**. Wiele wierszy na `market_id`.

Kolumny (SNAPSHOT_FIELDS):

- `snapshot_ts` – czas pobrania danych (po stronie naszej aplikacji).
- `market_id` – identyfikator rynku (klucz obcy do `markets_static`).
- `active` – czy rynek jest aktywny.
- `closed` – czy rynek jest zamknięty.
- `featured` – czy rynek jest wyróżniony.
- `new` – czy rynek jest nowy.
- `volume24hr` – obrót w ostatnich 24h.
- `volume1wk` – obrót w ostatnim tygodniu.
- `volume1mo` – obrót w ostatnim miesiącu.
- `volume1yr` – obrót w ostatnim roku.
- `volume_total` – całkowity obrót (life-time).
- `liquidity` – aktualna płynność.
- `liquidityAmm` – płynność z AMM.
- `liquidityClob` – płynność z CLOB.
- `openInterest` – otwarte pozycje.
- `lastTradePrice` – ostatnia cena transakcji.
- `bestBid` – najlepsza oferta kupna.
- `bestAsk` – najlepsza oferta sprzedaży.
- `spread` – rozpiętość bid-ask (jeśli dostępna).
- `oneDayPriceChange` – zmiana ceny 24h.
- `oneWeekPriceChange` – zmiana ceny tydzień.
- `commentCount` – liczba komentarzy.
- `competitive` – miara konkurencyjności.
- `score` – wewnętrzny score rynku.

---

## Zakres analiz ML

1. **Klasyfikacja**  
   - Cel: przewidzieć, czy rynek przekroczy określony próg `volume24hr` (np. 100k USD).  
   - Typ: model klasyfikacji binarnej (np. Random Forest / XGBoost).

2. **Regresja**  
   - Cel: przewidzieć wartość `volume24hr` (lub innej miary zaangażowania) na kolejny dzień.  
   - Typ: model regresji (XGBoost / LightGBM / regresja liniowa).

3. **Klasteryzacja**  
   - Cel: podział rynków na segmenty (np. wysokie volume / niska płynność / niski spread / nowe vs stare).  
   - Typ: algorytmy nienadzorowane (K-Means, DBSCAN).


---

## Miejsce na strukturę projektu (do uzupełnienia)

Docelowa struktura repozytorium zostanie uzupełniona, gdy kod kolektora, notebooki i modele będą gotowe. Poniżej szkic:

```text
.
├── data/
│   ├── markets_static.csv
│   ├── markets_snapshots.csv
│   └── ...
├── src/
│   ├── ...
│   └── ...
├── notebooks/
│   ├── ...
│   └── ...
├── README.md
└── ...