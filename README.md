# Aalto-yliopisto Junior Valinta-apuri

> [!WARNING]
> Valinta-apuri projekti on vielä kehitteillä. Menossa on koevaihe ja Valinta-apuriin tehdään vielä korjauksia, parannuksia ja muutoksia!

## Valinta-apuri?

### Mikä on valinta-apuri?

Aalto-yliopisto Juniorin valinta-apuri auttaa sinua löytämään sopivia ja kiinnostavia työpajoja monipuolisesta työpajavalikoimastamme!

### Mistä löydän valinta-apurin?

Aalto-yliopisto Junior Valinta-apuriin pääset [tästä](https://)!

## Toiminta

### Rakenne

Perustuu kahteen python tiedostoon. [bg.py](/bg.py) on taustalla toimiva dataa päivittävä prosessi joka kommunikoi sharepointin kanssa. [app.py](/app.py) on itse palvelin yhdessä [Gunicorn](https://gunicorn.org/) WSGI palvelimen kanssa.

Taustaprosessi tarvitsee environment variableja autentikaatioon MS Graphin kanssa ladatatakseen tiedostot sharepointista.

### Docker

Projekti toimii yhdellä Docker composella. Compose käynnistää ensin [bg.py](bg.py), joka hakee ja prosessoi datan, ja sen jälkeen Gunicornin, joka ajaa [app.py](app.py):n HTTP:n yli. Compose käynnistää myös Rediksen, joka tuo dataa taustaprosessista varsinaiselle palvelinprosessille. Composessa on myös Caddy reverse proxy, johon HTTPS liikenteen hallinta on siirretty. Caddyn ei tarvitse välttämättä olla samassa composessa, mutta tämän projektin yksinkertaisuuden vuoksi se on sinne lisätty.

Toiminta menee käytännössä näin:

1. bg.py lukee sharepointista dataa (Excel tiedosto).
2. Tämän datan bg käsittelee ja siirtää Redikseen. Bg myös lukee ja kompressoi kuvat ja tallentaa nämä.
3. app.py Lukee rediksestä tiedot ja levylle tallennetut kuvat.
4. app tarjoilee gunicornin kanssa HTTP liikennettä Caddylle
5. Caddy tarjoaa tämän eteenpäin HTTPS liikenteenä.

Mukana olevat Docker-tiedostot:

1. [Dockerfile](Dockerfile)
2. [docker-compose.yml](docker-compose.yml) testaus/dev tiedosto. Tämä ei käytä caddyä ja sisältää lyhyen python skriptin HTTP liikenteen siirtämiseen HTTPS puolelle.
3. [docker-compose.wproxy.yml](docker-compose.wproxy.yml) varsinainen dockerin compose tiedosto jossa on caddy mukana.

Esimerkkikäyttö:

```bash
docker compose -f docker-compose.wproxy.yml up --build -d
docker compose -f docker-compose.yml up --build -d

```

Tarvitset ennen käynnistystä ympäristömuuttujat `CLIENT_ID`, `CLIENT_SECRET`, `TENANT_ID` ja `DRIVE_ID`, sekä sertifikaatit `certs/cert.pem` ja `certs/key.pem`.

Paikallinen build (käyttäen buildx) ja vienti:

```bash
docker buildx build --platform linux/amd64 -t valinta-apuri:latest --load .
docker save valinta-apuri:latest -o valinta-apuri.tar
gzip valinta-apuri.tar
```

Siirrä palvelimelle valinta-apuri.tar, docker-compose.wproxy.yml ja /certs/*. Tämän jälkeen voidaan ladata kontti ja käyttää sitä.

```bash
gunzip valinta-apuri.tar.gz
sudo docker load -i valinta-apuri.tar
sudo docker compose -f docker-compose.wproxy.yml up -d
```

#### Kehityksen itse allekirjoitettu sertifikaatti

Devausta varten käytä omaa paikallista sertifikaattia, älä tuotannon sertifikaattia.

Helpoin tapa on luoda sellainen mukana tulevalla skriptillä:

```bash
sh scripts/create-dev-cert.sh
```

Se luo tiedostot `certs/cert.pem` ja `certs/key.pem`, jotka Compose mounttaa kontille. Sertifikaatti sisältää `localhost`- ja `127.0.0.1`-osoitteet, joten selain hyväksyy sen teknisesti oikeaan hostiin yhdistäessäsi. Selain silti näyttää varoituksen, koska sertifikaatti on itse allekirjoitettu.

Jos haluat poistaa certit myöhemmin, riittää että poistat `certs/`-kansion sisällön ja luot sen uudelleen tarvittaessa.

### Konfigurointi

Konfigurointi tapahtuu kahden tiedoston kautta: .env ja /caddy/Caddyfile. Näitä kumpaakaan ei ole repositoryssä mukana.

**.env** tiedostossa määritetään lähinnä bg:n käyttämiä tietoja sharepointtia varten.

```ini
ENV = "production"
CLIENT_ID = "..."
CLIENT_SECRET = "..."
TENANT_ID = "..."
DRIVE_ID = "..."
```

**/caddy/Caddyfile** tiedostossa määritetään Caddyn reverse proxyn asetukset ja myös HTTP -> HTTPS.

```nginx
{
    auto_https off
}

http://yourdomain.domain.com {
    redir https://yourdomain.domain.com{uri} 301
}

https://yourdomain.domain.com {
    tls /etc/caddy/certs/cert.pem /etc/caddy/certs/key.pem

    log {
        output file /var/log/caddy/access.log
        format json
    }

    reverse_proxy web:8000 {
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }
}
```

### Lokitiedot

Lokitietoja voi tarkastella alla olevilla komennoilla. Ensimmäinen komento antaa docker projektin elementit ja siitä SERVICE sarakkeesta voidaan katsoa xxx kohtaan laitettava tunnus. Toinen komento antaa lokitiedot 10h ajalta ja kolmas komento tarkastelee lokitietoja reaaliaikaisena.

```bash
sudo docker compose ps
sudo docker compose logs --since=10h xxx
sudo docker compose logs -f xxx
```

## Todo

- [X] HTTP/2 protokolla
- [x] preload/preconnect .css ja fonteille (myös BG.webp)
- [x] Cache-Controll implementaatio kuville yms.
- [x] Kuvat .jpg -> .webp
- [ ] ~~Vaihto palvelimella renderöidystä html tiedostosta javascriptiin~~
- [x] Vahdettu HTMX pohjaiseen toteukseen, joka mahdollistaa sivun sisällön vaihtamisen. Eli ei tarvitse ladata koko sivua uudelleen.
- [ ] Vaihto polling pohjaisesta taustaprorssista webhookkiin
