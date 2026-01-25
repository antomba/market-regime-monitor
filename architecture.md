market-regime-monitor/
│
├── data/
│   ├── latest.json        ← ТЕКУЩИЙ СИГНАЛ (для бота)
│   ├── history.csv        ← ИСТОРИЯ
│
├── scripts/
│   └── build_signals.py   ← Python: данные + логика
│
├── docs/                  ← GitHub Pages
│   ├── index.html
│   ├── app.js
│   └── styles.css
│
├── .github/workflows/
│   └── daily.yml          ← daily update
│
├── requirements.txt
└── README.md