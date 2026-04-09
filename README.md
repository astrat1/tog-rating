# TOG Rating

TOG Rating is a Home Assistant custom integration that turns an indoor temperature sensor and a weather entity into child clothing guidance with current, day, and night TOG recommendations. An outdoor temperature sensor can also be supplied if you want to override the weather entity's current temperature, and outdoor influence is configurable.

## Companion repositories

- Dashboard card: https://github.com/Anton2079/lovelace-tog-rating-card

## Screenshot

![TOG Rating cards](assets/tog-rating-screenshot-main.png)

![TOG Rating current and forecast cards](assets/tog-rating-screenshot.png)

![TOG Rating entities and device view](assets/tog-rating-screenshot-2.png)

## HACS repository type

Add this repository to HACS as an `Integration` repository.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Anton2079&repository=tog-rating&category=integration)

## Recommended GitHub repository settings

- Repository name: `tog-rating`
- Description: `Home Assistant integration for child clothing and TOG recommendations using indoor, weather, and optional outdoor temperature data.`
- Topics: `home-assistant`, `hacs`, `home-assistant-integration`, `tog`, `weather`, `parenting`

## What this repo contains

- `custom_components/tog_rating/`
- `hacs.json`
- HACS validation workflow
- brand icon in `brands/tog_rating/icon.png`

## Installation

1. In HACS, add this repository as a custom repository.
2. Choose repository type `Integration`.
3. Install `TOG Rating`.
4. Restart Home Assistant.
5. Go to Settings > Devices & Services and add `TOG Rating`.

## Companion dashboard card

This integration repo does not install the Lovelace card. Install the companion dashboard card from:

- https://github.com/Anton2079/lovelace-tog-rating-card