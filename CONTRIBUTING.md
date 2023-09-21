# Współtworzenie
## Wprowadzenie
Zapoznaj się z [Wymaganiami](#wymagania) oraz [Strukturą plików](#struktura-plików).

- Przed wprowadzaniem jakichkolwiek zmian, przetestuj swój kod, używając [Pyright'a](https://microsoft.github.io/pyright/#/).

- Staraj się dzielić pull requesty tak, aby nie były one duże. Zamiast robić jeden,
w którym wprowadzisz dużo rzeczy, podziel to na kilka pull requestów.

> Zobacz [Instalacja](#instalacja)

## Wymagania
- Zainstalowany [Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git).
- Python `3.9` lub nowszy.
- Znajomość Pythona i Githuba.

## Struktura plików
Bot jest aktualnie podzielony na 2 główne sekcje.

- `Commands`
- `Events`

W `Commands` jak można się domyślić, znajdują się komendy podzielone jednak na poszczególne podkategorie.
Natomiast w `Events` znajdują się eventy.

**W folderze `Data` znajduję się plik `config.json` należy go uzupełnić przed uruchomieniem bota.
Nie wszystkie dane muszą być uzupełnione, aby bot działał poprawnie.**

## Instalacja
- Najpierw utwórz swój [fork](https://docs.github.com/en/get-started/quickstart/fork-a-repo) reprozytorium.

```sh
git clone https://github.com/<your-username>/SmiffyBot
cd SmiffyBot

pip install -U -r requirements.txt
# Przed uruchomieniem bota uzupełnij dane w configu (Data/config.json)
python3 bot.py
```
