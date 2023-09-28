# Contributing
## Introduction
Take a look at [Requirements](#requriements) and [Project structure](#project-structure).

- Before making any pull requests, test your code using [Pyright](https://microsoft.github.io/pyright/#/).


- Try to split pull requests so that they are not large. Instead of making one,
in which you introduce a lot of stuff, separate them into several.

> See [Installation.](#installation)

## Requriements
- Installed [Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git).
- Python `3.9` or never.
- Knowledge of Python and Github.

## Project structure
Bot is currently organized into 2 main sections.

- `Commands`
- `Events`

In `Commands`, as you can guess, there are commands classified, into individual subcategories.

Meanwhile, in `Events` there are events xD.

**In the `Data` folder there is a `config.json` file that should be completed before the bot is launched.
Not all data must be filled for the bot to work properly.**

## Installation
- first of all, create your repository [fork](https://docs.github.com/en/get-started/quickstart/fork-a-repo)

```sh
git clone https://github.com/<your-username>/SmiffyBot
cd SmiffyBot

pip install -U -r requirements.txt
# Before running the bot, fill the data in the config (Data/config.json)
python3 bot.py
```
