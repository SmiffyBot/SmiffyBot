
# 🤖 SmiffyBot
![](https://img.shields.io/github/commit-activity/w/SmiffyBot/SmiffyBot?style=for-the-badge&color=%232289e0)
![](https://img.shields.io/github/languages/top/SmiffyBot/SmiffyBot?style=for-the-badge&color=%232289e0)
![](https://img.shields.io/github/license/SmiffyBot/SmiffyBot?style=for-the-badge&color=%232289e0)


## O Projekcie
- Smiffy jest to Polski bot discord, który pierwotnie miał być przeznaczony na jeden serwer.
Jednakże jesteśmy gdzie jesteśmy i jest aktualnie na ponad 1600 serwerach.

- Niedawno postanowiłem, że upublicznię projekt dla każdego, ponieważ uważam to za całkiem udany projekt a niestety, ale ostatnio nie mam już dla niego zbytnio czasu - Być może znajdzie się osoba, która będzie mi w stanie pomóc w udoskonalaniu bota.


## Biblioteka nextcord
- Bot bazuję głównie na nextcordzie (forku Discord.py), ale duża część kodu została usunięta lub zmieniona właśnie pod bota. Dla przykładu cała implementacja komend prefixowych czy nawet całe obiekty takie jak `Context` zostały usunięte.

- System cache'u też został delikatnie zmieniony, tak, aby metody, które wykonują zapytania HTTP `(.fetch)` po otrzymaniu odpowiedzi automatycznie dodawały obiekt do cache'u.

- Edytowaną wersję nextcorda możecie zobaczyć pod tym [linkiem](https://github.com/SmiffyBot/nextcord/tree/Smiffy).

## Współtworzenie
- Każdy bez wyjątku może został developerem bota. Wymagam jedynie przyzwoitej wiedzy języka Python, jak i umiejętność pisania botów, aby dowiedzieć się więcej, przeczytaj [contribution.md]().
