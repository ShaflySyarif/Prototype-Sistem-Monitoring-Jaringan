# Network Monitoring System

Prototype sistem monitoring jaringan yang dirancang untuk membantu memantau kondisi perangkat jaringan pada suatu lingkungan, seperti router, switch, access point, maupun perangkat jaringan lainnya berdasarkan IP Address.

Sistem melakukan monitoring secara berkala terhadap perangkat yang telah didaftarkan dan menampilkan status koneksi, latency, riwayat monitoring, grafik, serta alert ketika perangkat mengalami gangguan.

---

## 📌 Latar Belakang

Gangguan jaringan seperti koneksi terputus atau perangkat tidak dapat diakses dapat menghambat aktivitas operasional. Oleh karena itu, diperlukan sistem monitoring yang dapat memberikan informasi kondisi jaringan secara terpusat dan mudah dipahami.

Prototype ini dikembangkan sebagai bagian dari proyek monitoring jaringan pada lingkungan **Dinas Komunikasi dan Informatika (Diskominfo)**.

Konsep sistem disesuaikan dengan topologi jaringan yang menggunakan satu router utama MikroTik, switch sebagai perangkat distribusi, dan access point Ruijie pada ruangan-ruangan.

Gambaran umum topologi:

```text
                         INTERNET
                            │
                            ▼
                    ┌──────────────┐
                    │    MikroTik  │
                    │ Router Utama │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │    Switch    │
                    │   Distribusi │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
          Ruangan A    Ruangan B    Ruangan C
          Ruijie AP    Ruijie AP    Ruijie AP
```

> **Catatan:** Topologi di atas merupakan gambaran umum berdasarkan informasi yang diperoleh. Implementasi aktual menyesuaikan konfigurasi jaringan di lokasi.

---

## 🎯 Tujuan

Sistem ini bertujuan untuk:

- Memantau kondisi perangkat jaringan secara berkala.
- Mengetahui apakah perangkat dapat dijangkau atau tidak.
- Mengukur latency perangkat.
- Menyimpan riwayat hasil monitoring.
- Menampilkan grafik hasil monitoring.
- Memberikan alert ketika perangkat mengalami gangguan.
- Memudahkan pengguna mengetahui perangkat yang mengalami masalah melalui dashboard.
- Memungkinkan pengguna menambahkan perangkat baru berdasarkan IP Address.

---

## ⚙️ Cara Kerja Sistem

Secara umum, sistem bekerja dengan alur berikut:

```text
                    ┌───────────────┐
                    │     User      │
                    └───────┬───────┘
                            │
                            ▼
                  Tambahkan perangkat
                     IP Address
                            │
                            ▼
                  ┌─────────────────┐
                  │ Data Perangkat  │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Monitoring      │
                  │ Service         │
                  └────────┬────────┘
                           │
                           ▼
                    Ping IP Target
                           │
                    ┌──────┴──────┐
                    │             │
                 Berhasil       Gagal
                    │             │
                    ▼             ▼
                Hitung        Status
                Latency       Offline
                    │             │
                    └──────┬──────┘
                           │
                           ▼
                     Simpan Log
                           │
                           ▼
                    Dashboard Web
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
          Status        Latency         Grafik
             │             │             │
             └─────────────┼─────────────┘
                           ▼
                         Alert
```

### 1. Menambahkan Perangkat

Pengguna dapat menambahkan perangkat melalui dashboard dengan memasukkan:

- Nama/lokasi perangkat
- IP Address perangkat

Contoh:

```text
Nama/Lokasi : Router Utama
IP Address  : 192.168.1.1
```

atau:

```text
Nama/Lokasi : AP Ruang Rapat
IP Address  : 192.168.1.10
```

Sistem tidak membatasi perangkat hanya pada router. Selama perangkat memiliki IP dan dapat dijangkau dari server monitoring, perangkat tersebut dapat dijadikan target monitoring.

---

### 2. Monitoring Berkala

Setelah perangkat ditambahkan, sistem akan melakukan pengecekan secara otomatis dalam interval tertentu.

Contoh:

```text
IP Target
   │
   ▼
Ping
   │
   ▼
Tunggu interval
   │
   ▼
Ping kembali
   │
   ▼
Tunggu interval
   │
   ▼
...
```

Hasil setiap pengecekan akan dicatat sebagai log monitoring.

---

### 3. Pemeriksaan Koneksi

Sistem menggunakan mekanisme **ping** untuk mengetahui apakah perangkat dapat dijangkau.

Jika mendapatkan respons:

```text
ONLINE
```

Jika tidak mendapatkan respons setelah batas waktu tertentu:

```text
OFFLINE
```

Status tersebut kemudian ditampilkan pada dashboard.

---

### 4. Pengukuran Latency

Ketika perangkat memberikan respons terhadap ping, sistem akan mencatat waktu respons atau latency.

Contoh:

```text
Router Utama
Status  : ONLINE
Latency : 2 ms
```

Nilai latency dapat digunakan untuk melihat perubahan kualitas koneksi dari waktu ke waktu.

---

### 5. Penyimpanan Log

Setiap hasil monitoring disimpan sebagai riwayat.

Contoh:

```text
10:00:00 → ONLINE  → 2 ms
10:00:15 → ONLINE  → 3 ms
10:00:30 → ONLINE  → 2 ms
10:00:45 → ONLINE  → 4 ms
10:01:00 → OFFLINE
```

Riwayat tersebut digunakan untuk menampilkan kondisi perangkat dalam periode tertentu.

---

### 6. Grafik Monitoring

Data log dapat ditampilkan dalam bentuk grafik untuk membantu pengguna melihat perubahan latency.

Contoh konsep:

```text
Latency
  │
5 │       ●
4 │   ●       ●
3 │       ●
2 │ ●             ●
1 │
  └────────────────────
    Waktu →
```

Dengan grafik ini, pengguna dapat melihat apakah latency perangkat relatif stabil atau mengalami peningkatan.

---

### 7. Alert

Sistem menyediakan fitur alert untuk memberikan pemberitahuan ketika perangkat mengalami gangguan.

Contoh:

```text
🔴 ALERT

AP Ruang Rapat
IP: 192.168.1.10

Status: OFFLINE
```

Alert dapat diaktifkan atau dinonaktifkan oleh pengguna melalui dashboard.

---

## 🖥️ Dashboard

Dashboard dirancang agar dapat digunakan oleh pengguna non-teknis.

Informasi utama yang ditampilkan meliputi:

- Jumlah perangkat yang dimonitor.
- Jumlah perangkat online.
- Jumlah perangkat offline.
- Status masing-masing perangkat.
- Latency perangkat.
- Riwayat monitoring.
- Grafik latency.
- Alert perangkat.

Contoh tampilan konseptual:

```text
┌──────────────────────────────────────────────────┐
│          NETWORK MONITORING DASHBOARD            │
├──────────────────────────────────────────────────┤
│                                                  │
│  TOTAL       ONLINE       OFFLINE                │
│    10           9            1                   │
│                                                  │
├──────────────────────────────────────────────────┤
│ Perangkat              Status       Latency      │
│                                                  │
│ Router Utama            🟢 ONLINE       2 ms     │
│ Switch Lantai 1        🟢 ONLINE       1 ms     │
│ AP Ruang A              🟢 ONLINE       3 ms     │
│ AP Ruang B              🔴 OFFLINE       -       │
│ AP Ruang C              🟢 ONLINE       4 ms     │
│                                                  │
└──────────────────────────────────────────────────┘
```

---

## 🏗️ Arsitektur Sistem

Prototype menggunakan pendekatan monitoring terpusat.

```text
                    ┌────────────────────┐
                    │       USER         │
                    │    Diskominfo      │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │   Web Dashboard    │
                    │    index.html      │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │   Backend Server   │
                    │      app.py        │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │ Monitoring Service │
                    │       Ping         │
                    └─────────┬──────────┘
                              │
             ┌────────────────┼────────────────┐
             │                │                │
             ▼                ▼                ▼
        MikroTik           Switch          Ruijie AP
        Router             Distribusi       Ruangan
```

Pada prototype, server monitoring melakukan pengecekan terhadap IP Address perangkat yang telah didaftarkan.

---

### `app.py`

Berfungsi sebagai backend utama sistem.

Tanggung jawabnya antara lain:

- Menjalankan web server.
- Mengelola perangkat yang dimonitor.
- Melakukan proses monitoring.
- Melakukan ping terhadap IP target.
- Menghitung latency.
- Menyimpan log.
- Menyediakan data monitoring kepada dashboard.
- Mengelola konfigurasi alert.

### `index.html`

Merupakan antarmuka dashboard yang digunakan oleh user.

Digunakan untuk:

- Melihat status perangkat.
- Menambahkan perangkat.
- Mengedit perangkat.
- Melihat detail perangkat.
- Melihat log.
- Melihat grafik.
- Mengaktifkan/nonaktifkan alert.

---

## ⏱️ Monitoring Interval

Sistem melakukan monitoring secara berkala.

Untuk penyimpanan riwayat, prototype menggunakan interval monitoring yang memungkinkan data mencakup kurang lebih **30 menit**, sehingga pengguna dapat melihat perubahan kondisi jaringan dalam periode tersebut.

Interval dapat disesuaikan melalui konfigurasi program.

---

## 🔔 Sistem Alert

Alert dapat diaktifkan dan dinonaktifkan melalui dashboard.

```text
Alert OFF
   │
   │ User mengaktifkan
   ▼
Alert ON
   │
   │ Perangkat OFFLINE
   ▼
Peringatan ditampilkan
   │
   │ User menonaktifkan
   ▼
Alert OFF
```

---

## 🛠️ Teknologi yang Digunakan

Prototype ini menggunakan:

- **Python** — Backend dan proses monitoring.
- **HTTP Server** — Menyediakan dashboard dan API.
- **HTML/CSS/JavaScript** — Frontend dashboard.
- **ICMP Ping** — Pengecekan keterjangkauan perangkat.
- **JSON** — Penyimpanan data/log pada prototype.

---

## 🚀 Cara Menjalankan

### 1. Clone Repository

```bash
git clone https://github.com/USERNAME/Prototype-Sistem-Monitoring-Jaringan.git
```

Masuk ke folder:

```bash
cd Prototype-Sistem-Monitoring-Jaringan
```

### 2. Pastikan Python Telah Terinstall

Cek dengan:

```bash
python --version
```

atau:

```bash
py --version
```

### 3. Jalankan Program

```bash
python app.py
```

Jika berhasil, server akan menampilkan alamat seperti:

```text
Network Monitoring:
http://127.0.0.1:5000
```

Buka alamat tersebut melalui browser.

---

## 📋 Contoh Penggunaan

Misalnya jaringan memiliki:

```text
Router MikroTik
IP: 192.168.1.1

Switch Lantai 1
IP: 192.168.1.2

AP Ruang Rapat
IP: 192.168.1.10
```

User dapat memasukkan ketiga perangkat tersebut ke dashboard.

Sistem kemudian melakukan:

```text
192.168.1.1 → Ping → Status + Latency
192.168.1.2 → Ping → Status + Latency
192.168.1.10 → Ping → Status + Latency
```

Hasilnya ditampilkan secara terpusat pada dashboard.

---

## ⚠️ Catatan Penting

Status `OFFLINE` pada sistem berarti **IP target tidak mendapatkan respons dari server monitoring**.

Hal tersebut tidak selalu berarti perangkat benar-benar rusak atau internet sedang mati.

Kemungkinan penyebab antara lain:

- Perangkat memang mati.
- Koneksi jaringan terputus.
- IP tidak dapat dijangkau dari server monitoring.
- Firewall memblokir ICMP/ping.
- Perubahan konfigurasi jaringan.
- Masalah routing antar jaringan.

Oleh karena itu, hasil monitoring perlu dipahami berdasarkan topologi jaringan yang digunakan.

---

## 🔮 Pengembangan Selanjutnya

Prototype ini masih dapat dikembangkan dengan fitur:

- Monitoring bandwidth.
- Packet loss monitoring.
- Monitoring uptime.
- Monitoring kualitas internet.
- Monitoring penggunaan CPU/memory perangkat.
- SNMP monitoring.
- Notifikasi melalui Telegram/WhatsApp/Email.
- Penyimpanan database.
- Multi-user authentication.
- Agent monitoring pada lokasi berbeda.
- Deployment pada server/cloud.
- Monitoring real-time dengan WebSocket.

---

## 📌 Status Project

**Project Status:** Prototype / Development

Project ini dikembangkan sebagai prototype sistem monitoring jaringan untuk membantu pemantauan kondisi perangkat jaringan secara terpusat.

---

## 👨‍💻 Developer

Developed as part of a network monitoring project for:

**Dinas Komunikasi dan Informatika (Diskominfo)**

### Project Focus

> **Rancang Bangun Prototype Sistem Monitoring Jaringan pada Dinas Kominfo**
