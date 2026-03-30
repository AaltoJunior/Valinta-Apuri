# Aalto-yliopisto Junior Valinta-apuri

> [!WARNING]
> Valinta-apuri projekti on vielä kehitteillä eikä ole valmis laajaan käyttöön!

## Valinta-apuri?

### Mikä on valinta-apuri?

Aalto-yliopisto Juniorin valinta-apuri auttaa sinua löytämään sopivia ja kiinnostavia työpajoja monipuolisesta työpajavalikoimastamme!

### Mistä löydän valinta-apurin?

Aalto-yliopisto Junior Valinta-apuriin pääset [tästä](https://)!

## Toiminta

### Rakenne

Perustuu kahteen pyhon tiedostoon. [bg.py](/bg.py) on taustalla toimiva dataa päivittävä prosessi joka kommunikoi sharepointin kanssa. [app.py](/app.py) on itse palvein yhdessä [Gunicor](https://gunicorn.org/) WSGI palvelimen kanssa.

Taustaprosessi tarvitsee environmet variableja autentikaatioon MS Graphin kanssa ladatatakseen tiedostot teamssista.

``` sh
CLIENT_ID = ""
CLIENT_SECRET = ""
TENANT_ID = ""
DRIVE_ID = ""
```

Nämä voivat olla .env tiedostossa kehittämistä varten. Jos `ENV = "prudction` ei ole määritelty luetaan muuttujat .env tiedostosta.

### Konfigurointi ja suorittaminen
Molemmat python tiedostot määritetään systemd kautta serviceiksi.

Ennnen kun prosesseja voidaan suorittaa tätytyy asetaa vaatimukset:

```bash
pip3.12 install -r requirements.txt
```

Luodaan taustaprosessin tiedosto:

```bash
sudo nano /etc/systemd/system/bg.service
```

bg.service tiedoston sisältö:

```ini
[Unit]
Description=Valita-apuri Background Data Updater
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/Valinta-apuri

Environment="ENV=production"
Environment="CLIENT_ID="
Environment="CLIENT_SECRET="
Environment="TENANT_ID="
Environment="DRIVE_ID="

ExecStart=/usr/bin/python3.12 -u bg.py

Restart=always
RestartSec=5

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Luodaan palvelinprosessin tiedosto:

```bash
sudo nano /etc/systemd/system/gunicorn.service
```

bg.service tiedoston sisältö:

```ini
[Unit]
Description=Valinta-apuri Gunicorn Service
After=network.target bg.service
Requires=bg.service

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/Valinta-Apuri/

Environment="ENV=production"

ExecStart=/usr/bin/python3.12 -m gunicorn \
    --worker-class gthread \
    --threads 4 \
    --workers 2 \
    --bind 0.0.0.0:443 \
    --certfile cert.pem \
    --keyfile key.pem \
    --error-logfile - \
    --http-protocols h2,h1 \
    app:app

Restart=always
RestartSec=5

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

HTTPS palvelinta varten tarvitaan sertifikaatti joka sisältää cert.pem ja key.pem tiedostot, sekä avoin portti 443. Portin voi avata esimerkisi:

```bash
sudo firewall-cmd --add-port=443/tcp --permanent
```

Ja väliaikaisen sertifikaation voi luoda komennolla:

```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -sha256 -days 365 -nodes
```

Käynnistys:

```bash
sudo systemctl start bg.service
sudo systemctl start gunicorn.service
```

Sammuttaminen:

```bash
sudo systemctl stop gunicorn.service
sudo systemctl stop bg.service
```

Uudelleenkäynnistys:

```bash
sudo systemctl restart bg.service
sudo systemctl restart gunicorn.service
```

Satuksen tarkastaminen:

```bash
systemctl status bg.service
systemctl status gunicorn.service
```

Automaattinen käynnistys:

```bash
sudo systemctl enable bg.service
sudo systemctl enable gunicorn.service
```

Automaattisen käynnistyksen tarkastus:

```bash
systemctl is-enabled bg.service
systemctl is-enabled gunicorn.service
```

Muokkaaminen:

```bash
sudo nano /etc/systemd/system/bg.service
sudo nano /etc/systemd/system/gunicorn.service
```

Jonka jälkeen:

```bash
sudo systemctl daemon-reload

sudo systemctl restart bg.service
sudo systemctl restart gunicorn.service
```

Logi tiedostojen tarkastelu:

```bash
journalctl -u bg.service -f
journalctl -u gunicorn.service -f
```

## Todo

- [X] HTTP/2 protokolla
- [ ] preload/preconnect .css ja fonteille
- [ ] Vaihto palvelimella renderöidystä html tiedostosta javascriptiin
- [ ] Vaihto polling pohjaisesta taustaprorssista webhookkiin
