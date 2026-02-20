# Weather Bot

Discord bot that generates styled weather widgets using OpenWeatherMap API and browser rendering.

## Main Features

- `/weather <city>` - Get weather widget with dynamic styling based on conditions
- `/ping` - Check bot latency
- `/render` - Test widget rendering
- Automatic theming for Clear ☀️, Clouds ☁️, Rain 🌧️, Snow ❄️, etc.

## How It Works

Bot fetches weather data via OpenWeatherMap API, replaces placeholders in HTML template with city temperature, feels-like temp, humidity, wind speed, pressure, and condition-based styling (colors, icons, gradients). Playwright renders HTML to PNG screenshot and sends as Discord attachment.

[Add bot](https://discord.com/oauth2/authorize?client_id=1473090401551253565&permissions=100352&integration_type=0&scope=bot)
