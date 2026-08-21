#include <Arduino.h>
#include <math.h>

constexpr uint8_t ECG_PIN = 35;
constexpr uint32_t SAMPLE_PERIOD_US = 4000; // 250 Hz
constexpr int FS_HZ = 250;
constexpr int MWI_WINDOW = 38;              // 150 ms at 250 Hz, rounded
constexpr int ZERO_SAMPLES = 75;            // 2 * maxQRSduration
constexpr int REFRACTORY_SAMPLES = 75;      // 300 ms
constexpr int MIN_MISSED_DISTANCE = 62;     // 250 ms
constexpr int BENCH_WINDOW = 1000;

class PanTompkinsQrs {
 public:
  void begin(float firstSample) {
    x1 = firstSample;
    x2 = firstSample;
  }

  bool update(float sample, uint32_t sampleIndex, uint32_t &qrsSampleIndex, float &thresholdOut) {
    const float y = 0.11216024f * sample - 0.11216024f * x2 + 1.73356294f * y1 - 0.77567951f * y2;
    x2 = x1;
    x1 = sample;
    y2 = y1;
    y1 = y;

    const float diff = y - lastFiltered;
    lastFiltered = y;
    const float squared = diff * diff;

    mwiSum -= mwiBuffer[mwiPos];
    mwiBuffer[mwiPos] = squared;
    mwiSum += squared;
    mwiPos = (mwiPos + 1) % MWI_WINDOW;
    if (mwiCount < MWI_WINDOW) {
      mwiCount++;
    }
    float mwi = mwiSum / static_cast<float>(mwiCount);
    if (sampleIndex < ZERO_SAMPLES) {
      mwi = 0.0f;
    }

    const bool isPeak = (prevMwi > prevPrevMwi) && (prevMwi > mwi);
    const uint32_t peakIndex = sampleIndex > 0 ? sampleIndex - 1 : 0;
    bool detected = false;
    if (isPeak) {
      recentPeaks[recentPeakPos] = {peakIndex, prevMwi};
      recentPeakPos = (recentPeakPos + 1) % MAX_RECENT_PEAKS;
      if (recentPeakCount < MAX_RECENT_PEAKS) {
        recentPeakCount++;
      }

      if (prevMwi > thresholdI1 && (peakIndex - lastSignalPeak) > REFRACTORY_SAMPLES) {
        const uint32_t previousSignalPeak = lastSignalPeak;
        lastSignalPeak = peakIndex;
        spki = 0.125f * prevMwi + 0.875f * spki;
        detected = true;

        if (rrMissed > 0 && previousSignalPeak > 0 && (lastSignalPeak - previousSignalPeak) > rrMissed) {
          uint32_t missedIndex = 0;
          float missedValue = 0.0f;
          for (int i = 0; i < recentPeakCount; ++i) {
            const Peak p = recentPeaks[i];
            if (p.index > previousSignalPeak + MIN_MISSED_DISTANCE &&
                p.index + MIN_MISSED_DISTANCE < lastSignalPeak &&
                p.value > thresholdI2 &&
                p.value > missedValue) {
              missedIndex = p.index;
              missedValue = p.value;
            }
          }
          if (missedIndex > 0) {
            lastSignalPeak = missedIndex;
          }
        }

        if (previousSignalPeak > 0) {
          const uint32_t rr = lastSignalPeak - previousSignalPeak;
          rrBuffer[rrPos] = rr;
          rrPos = (rrPos + 1) % 8;
          if (rrCount < 8) {
            rrCount++;
          }
          if (rrCount == 8) {
            uint32_t sum = 0;
            for (int i = 0; i < 8; ++i) {
              sum += rrBuffer[i];
            }
            rrMissed = static_cast<uint32_t>(1.66f * (sum / 8.0f));
          }
        }
      } else {
        npki = 0.125f * prevMwi + 0.875f * npki;
      }
      thresholdI1 = npki + 0.25f * (spki - npki);
      thresholdI2 = 0.5f * thresholdI1;
    }

    prevPrevMwi = prevMwi;
    prevMwi = mwi;
    thresholdOut = thresholdI1;
    if (detected) {
      qrsSampleIndex = lastSignalPeak;
    }
    return detected;
  }

 private:
  struct Peak {
    uint32_t index;
    float value;
  };
  static constexpr int MAX_RECENT_PEAKS = 64;
  float x1 = 0.0f;
  float x2 = 0.0f;
  float y1 = 0.0f;
  float y2 = 0.0f;
  float lastFiltered = 0.0f;
  float mwiBuffer[MWI_WINDOW] = {};
  int mwiPos = 0;
  int mwiCount = 0;
  float mwiSum = 0.0f;
  float prevPrevMwi = 0.0f;
  float prevMwi = 0.0f;
  float spki = 0.0f;
  float npki = 0.0f;
  float thresholdI1 = 0.0f;
  float thresholdI2 = 0.0f;
  uint32_t lastSignalPeak = 0;
  uint32_t rrMissed = 0;
  uint32_t rrBuffer[8] = {};
  int rrPos = 0;
  int rrCount = 0;
  Peak recentPeaks[MAX_RECENT_PEAKS] = {};
  int recentPeakPos = 0;
  int recentPeakCount = 0;
};

PanTompkinsQrs qrs;
uint32_t nextSampleUs = 0;
uint32_t sampleIndex = 0;
uint32_t lastRTimeMs = 0;
uint32_t rrMs = 0;
uint16_t bpm = 0;
uint16_t benchValues[BENCH_WINDOW] = {};
int benchCount = 0;

void reportBench() {
  if (benchCount < BENCH_WINDOW) return;
  uint16_t sorted[BENCH_WINDOW];
  memcpy(sorted, benchValues, sizeof(sorted));
  for (int i = 1; i < BENCH_WINDOW; ++i) {
    uint16_t key = sorted[i];
    int j = i - 1;
    while (j >= 0 && sorted[j] > key) {
      sorted[j + 1] = sorted[j];
      --j;
    }
    sorted[j + 1] = key;
  }
  uint32_t sum = 0;
  for (int i = 0; i < BENCH_WINDOW; ++i) sum += sorted[i];
  Serial.printf("QRS_BENCH,COUNT,%d,MEAN_US,%.2f,MED_US,%u,P95_US,%u,P99_US,%u,MAX_US,%u,BUDGET_US,4000\n",
                BENCH_WINDOW,
                static_cast<double>(sum) / BENCH_WINDOW,
                sorted[BENCH_WINDOW / 2],
                sorted[static_cast<int>(BENCH_WINDOW * 0.95f)],
                sorted[static_cast<int>(BENCH_WINDOW * 0.99f)],
                sorted[BENCH_WINDOW - 1]);
  benchCount = 0;
}

void setup() {
  Serial.begin(115200);
  delay(300);
  pinMode(ECG_PIN, INPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(ECG_PIN, ADC_11db);
  const int first = analogRead(ECG_PIN);
  qrs.begin(static_cast<float>(first));
  nextSampleUs = micros();
  Serial.println("ESP32 AD8232 Pan-Tompkins QRS route starting...");
}

void loop() {
  const uint32_t nowUs = micros();
  if (static_cast<int32_t>(nowUs - nextSampleUs) < 0) return;
  nextSampleUs += SAMPLE_PERIOD_US;

  const int raw = analogRead(ECG_PIN);
  uint32_t qrsIndex = 0;
  float threshold = 0.0f;
  const uint32_t t0 = micros();
  const bool detected = qrs.update(static_cast<float>(raw), sampleIndex, qrsIndex, threshold);
  const uint32_t elapsed = micros() - t0;
  if (benchCount < BENCH_WINDOW) {
    benchValues[benchCount++] = static_cast<uint16_t>(min<uint32_t>(elapsed, 65535));
  }
  reportBench();

  if (detected) {
    const uint32_t detectedMs = static_cast<uint32_t>((1000ULL * qrsIndex) / FS_HZ);
    if (lastRTimeMs > 0 && detectedMs > lastRTimeMs) {
      rrMs = detectedMs - lastRTimeMs;
      if (rrMs >= 250 && rrMs <= 2200) {
        bpm = static_cast<uint16_t>(60000UL / rrMs);
        Serial.printf("RR_MS,%lu,BPM,%u,TS_MS,%lu\n",
                      static_cast<unsigned long>(rrMs),
                      bpm,
                      static_cast<unsigned long>(detectedMs));
      }
    }
    lastRTimeMs = detectedMs;
  }

  sampleIndex++;
}
