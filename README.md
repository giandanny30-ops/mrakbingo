# 🎰 Squad Lutrija Bot — Python Edition (v5.0)

Discord bot sa 11 igara, ban sistemom i automatskim igrama svakih 5 minuta, redom jedna po jedna.

## ⚡ Šta je novo u v5.0

- **Svi embedi su sad na isti, jedinstveni "izgled"**: naslov `{emoji} Pokrenuo/la: {korisnik}`, veliki naslov igre ispisan razmaknutim slovima (npr. `🎱 💎 B I N G O 💎 🎱`), bullet lista sa 🎯/🪙/⏰ ikonicama, i footer u formatu `{emoji} x Squad Lutrija {Igra} • Ulog: X novca • danas u HH:MM` — identično na svih 11 igara i svim ostalim komandama (stanje, bonus, top, igre, ban, banlista, moj-ban).
- **Bingo ima "Nagradna Lista" tabelu** (kao pravi bingo) koja prikazuje isplate po broju izvlačenja.
- **Kolo Sreće se stvarno vrti** — kad klikneš Zavrti Kolo, poruka se nekoliko puta animira kroz nasumična polja (🌀 vrti se...) pa se tek onda zaustavi i otkrije dobitak/gubitak, umjesto da odmah ispiše rezultat.
- **"Nastavi Pjesmu"** i dalje prikazuje traženi dio pjesme krupnim tekstom čim igra počne, i traži da pogodiš nastavak.
- Ostalo iz v4.0 je zadržano: rosa akcent boja (pobjeda/gubitak i dalje zeleno/crveno), automatske igre idu redom svakih 5 min, svaka igra odmah pokazuje pravo stanje (pitanje/karte/tablu) čim počne, dnevni bonus sa nizom dana (streak), rang/titula na `/stanje`, `/moj-ban` i `/banlista` javno vidljivi, novac formatiran (`12.500`).

## ⚡ Brzi Start

```bash
pip install -r requirements.txt
cp .env.example .env
# popuni .env sa tvojim tokenima
python bot.py
```

## 🛠️ Setup

### 1. Napravi Discord Bot
1. [Discord Developer Portal](https://discord.com/developers/applications) → New Application
2. Bot tab → Add Bot → Reset Token (kopiraj)
3. Uključi: **Server Members Intent** + **Message Content Intent**

### 2. Popuni .env
```env
DISCORD_TOKEN=tvoj_token
DISCORD_GUILD_ID=id_servera
DISCORD_CHANNEL_ID=id_kanala_za_igre
DISCORD_BAN_CHANNEL_ID=id_ban_kanala
DISCORD_ANTI_BAN_ROLE_ID=id_uloge
DISCORD_OWNER_ID=tvoj_id
```

### 3. Pokretanje
```bash
python bot.py
```

Baza podataka (`squad_lutrija.db`) se automatski kreira (i automatski migrira ako već postoji od starije verzije).

## 🎮 Igre (11 ukupno, idu redom svakih 5 min)

🎰 Grebalice | 🎱 Bingo | 🎡 Kolo Sreće | ❓ Pitanje | 🎵 Nastavi Pjesmu | 🔷 Pogodi Oblik | 💣 Minsko Polje | 🃏 Blackjack | 🐉 Zmaj ili Vitez | 🎯 Pogodak | 🔢 Matematika

## 📋 Komande

### Slash Komande
| Komanda | Opis |
|---------|------|
| `/stanje` | Stanje novca, rang i statistika |
| `/bonus` | Dnevni bonus (raste sa nizom dana) |
| `/igre` | Lista svih igara |
| `/top` | Top 10 igrača |
| `/ban @korisnik razlog` | Banuj korisnika |
| `/unban user_id` | Odbanuj korisnika |
| `/banlista` | Lista aktivnih banova (javno) |
| `/moj-ban` | Tvoj ban status (javno) |

### Owner Prefix Komande (.)
| Komanda | Opis |
|---------|------|
| `.daijnovca @korisnik iznos` | Daj novac |
| `.uzminovca @korisnik iznos` | Uzmi novac |
| `.resetaj @korisnik` | Resetuj korisnika |
| `.pokreni` | Ručno pokreni sljedeću igru u redoslijedu |
| `.pomoc` | Lista komandi |

## ⚡ Anti-Ban
- 5 aktivnih banova → automatski skida ulogu (`DISCORD_ANTI_BAN_ROLE_ID`)
- Embed obavijest javno u ban kanal
- DM banovanom korisniku

## 🚀 Host na Replit
1. Napravi novi Python Repl (ili koristi postojeći)
2. Uploadaj `bot.py` i `requirements.txt`
3. Dodaj Secrets (🔒) sa svim vrijednostima iz `.env`
4. Klikni Run ▶️

## GitHub
```bash
git init
git add bot.py requirements.txt .env.example README.md .gitignore
git commit -m "🎰 Squad Lutrija Bot v4.0"
git remote add origin https://github.com/tvoje_ime/squad-lutrija.git
git push -u origin main
```
