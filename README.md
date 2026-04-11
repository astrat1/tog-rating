# TOG Rating

A Home Assistant custom integration that calculates age-appropriate sleep clothing recommendations for young children based on indoor temperature, outdoor weather data, humidity, and conditions.

> **Fork of [Anton2079/tog-rating](https://github.com/Anton2079/tog-rating)** — original integration by Anton2079. This fork adds multi-mode support, toddler blanket mode, automatic base layer recommendations, live helper entity reads, birthday-based milestone automations, and multi-child config flow support.

---

## Companion Card

Install the Lovelace dashboard card separately:

- Fork (matches this integration): [github.com/astrat1/lovelace-tog-rating-card](https://github.com/astrat1/lovelace-tog-rating-card)
- Original: [github.com/Anton2079/lovelace-tog-rating-card](https://github.com/Anton2079/lovelace-tog-rating-card)

---

## How It Works

The integration reads your indoor temperature sensor and weather entity every 15 minutes (or immediately when a tracked entity changes). It blends indoor and outdoor temperatures, applies humidity, wind, and precipitation adjustments, and maps the result to one of five clothing recommendation tiers.

### Temperature Blend

```
effective_temp = (indoor_temp × indoor_weight) + (outdoor_temp × outdoor_weight)
```

Outdoor weight is 10% by default (HVAC-controlled home). If any configured opening sensor has been open for more than 60 minutes, outdoor weight increases to 35%.

### Adjustment Factors

| Factor | Effect |
|---|---|
| High indoor humidity (>50%) | Warms effective temp |
| Low indoor humidity (<50%) | Cools effective temp |
| Wet weather conditions | -1.5°C |
| Windy conditions | -0.5°C |
| Wind speed 25–39 km/h | -1.0°C |
| Wind speed 40+ km/h | -2.0°C |
| Rain probability ≥60% | -0.5°C |
| Temperature offset helper | User-adjustable, ±3°C |

### Recommendation Tiers

| Effective Temp | Tier |
|---|---|
| ≥ 24°C (75°F) | Very Light |
| 22–24°C (71–75°F) | Light |
| 20–22°C (68–71°F) | Balanced |
| 17–20°C (63–68°F) | Warm |
| < 17°C (63°F) | Extra Warm |

Each tier has mode-specific clothing text. Base layer recommendations scale automatically with temperature — long-sleeve by default, short-sleeve when hot, footed or fleece when cold.

### Sleep Modes

| Mode | Typical Age | Notes |
|---|---|---|
| `baby` | 0–12 months | Cotton onesie always; sleep sack scaled to tier |
| `toddler` | 12–24 months | PJs + sleep sack |
| `toddler_blanket` | 18–24 months | Auto-activates when sleep sack boolean is off |
| `child` | 24+ months | PJs + blanket, no sleep sack |

### Sensors Created

Each integration instance creates three sensors named after the instance title:

| Sensor | Data source |
|---|---|
| Current | Live indoor + current outdoor temperature |
| Day | Daytime forecast (high or daytime twice-daily slot) |
| Night | Nighttime forecast (low or nighttime twice-daily slot) |

Each sensor exposes a full attribute set — see [Sensor Attributes](#sensor-attributes-reference).

---

## Installation

### Via HACS

[![Add to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=astrat1&repository=tog-rating&category=integration)

1. In HACS, go to **Integrations > Custom repositories**
2. Add `https://github.com/astrat1/tog-rating` and select type **Integration**
3. Install **TOG Rating**
4. Restart Home Assistant

### Manual

1. Copy the `custom_components/tog_rating/` folder into your `config/custom_components/` directory
2. Restart Home Assistant

---

## Configuration

Go to **Settings > Devices & Services > Add Integration** and search for **TOG Rating**.

### Required Fields

| Field | Description |
|---|---|
| Name | Label for this instance (e.g., "Nursery TOG") |
| Indoor temperature sensor | A `sensor` entity reporting °C or °F |
| Weather entity | A `weather` entity with forecast support |

### Optional Fields

| Field | Description |
|---|---|
| Indoor humidity sensor | Improves accuracy in dry or humid rooms |
| Opening sensors | Windows/doors — shifts outdoor weight when open |
| Sleep mode entity | Override default helper entity (for multi-child setups) |
| Bedding type entity | Override default helper entity |
| Temperature offset entity | Override default helper entity |

---

## Helper Entities

The integration reads helper entities at runtime. Create them in your HA configuration (YAML packages recommended). Changes to helper values take effect immediately without restarting.

### Sleep Mode (`input_select`)

Controls which clothing table is used. Options must be exactly `baby`, `toddler`, or `child`.

```yaml
input_select:
  child_sleep_mode:
    name: Child Sleep Mode
    options:
      - baby
      - toddler
      - child
    initial: baby
    icon: mdi:baby-face-outline
```

### Uses Sleep Sack (`input_boolean`)

When `off` with sleep mode set to `toddler`, activates blanket/sheet language instead of sleep sack language.

```yaml
input_boolean:
  child_uses_sleep_sack:
    name: Child Uses Sleep Sack
    initial: true
    icon: mdi:bag-personal-outline
```

### Temperature Offset (`input_number`)

Shifts all recommendations warmer or cooler. Use when the standard calculation consistently feels one tier off for your space.

```yaml
input_number:
  tog_temp_offset:
    name: TOG Temperature Offset
    min: -3.0
    max: 3.0
    step: 0.5
    initial: 0.0
    unit_of_measurement: "°C"
    icon: mdi:thermometer-plus
    mode: slider
```

### Child Birthday (`input_datetime`)

Required for milestone automations. Used only to calculate age locally — never leaves Home Assistant.

```yaml
input_datetime:
  child_birthday:
    name: Child Birthday
    has_date: true
    has_time: false
    icon: mdi:cake-variant
```

### Age in Months (template sensor)

```yaml
template:
  - sensor:
      - name: "Child Age Months"
        unique_id: child_age_months
        unit_of_measurement: months
        state: >
          {% set bd = states('input_datetime.child_birthday') %}
          {% if bd in ['unknown', 'unavailable', ''] %}
            unknown
          {% else %}
            {% set bdate = strptime(bd, '%Y-%m-%d') %}
            {% set today = now().date() %}
            {{ (today.year - bdate.year) * 12 + (today.month - bdate.month) }}
          {% endif %}
```

### Notification Helpers

```yaml
input_datetime:
  tog_bedtime_notification_time:
    name: TOG Bedtime Notification Time
    has_date: false
    has_time: true
    icon: mdi:bell-clock

input_select:
  tog_notification_target:
    name: TOG Notification Recipients
    options:
      - Parent 1 only
      - Parent 2 only
      - Both
    icon: mdi:cellphone-message

input_boolean:
  tog_transition_pending:
    name: TOG Mode Transition Pending
    icon: mdi:clock-alert-outline
```

---

## Milestone Automations

These automations send push notifications at key age milestones and handle the response actions.

### 12-Month Milestone — Baby to Toddler

```yaml
automation:
  - id: tog_milestone_12_months
    alias: TOG - 12-Month Milestone
    mode: single
    trigger:
      - platform: numeric_state
        entity_id: sensor.child_age_months
        above: 11
    condition:
      - condition: state
        entity_id: input_select.child_sleep_mode
        state: baby
    action:
      - service: input_boolean.turn_on
        target:
          entity_id: input_boolean.tog_transition_pending
      - service: notify.notify
        data:
          title: "Sleep Mode Update"
          message: >
            Your child is 1 year old. AAP guidelines support transitioning to
            toddler clothing recommendations. Switch now, or be reminded next month.
          data:
            actions:
              - action: TOG_SWITCH_TODDLER
                title: Switch to Toddler
              - action: TOG_REMIND_LATER
                title: Remind me in a month
```

### 18-Month Milestone — Sleep Sack Transition Advisory

```yaml
  - id: tog_milestone_18_months
    alias: TOG - 18-Month Milestone
    mode: single
    trigger:
      - platform: numeric_state
        entity_id: sensor.child_age_months
        above: 17
    condition:
      - condition: state
        entity_id: input_select.child_sleep_mode
        state: toddler
      - condition: state
        entity_id: input_boolean.child_uses_sleep_sack
        state: "on"
    action:
      - service: notify.notify
        data:
          title: "Sleep Mode Update"
          message: >
            Your child is 18 months. When ready to move away from the sleep sack,
            flip the "Uses Sleep Sack" toggle — recommendations switch to
            blanket/sheet language automatically.
```

### 24-Month Milestone — Toddler to Child Advisory

```yaml
  - id: tog_milestone_24_months
    alias: TOG - 24-Month Milestone
    mode: single
    trigger:
      - platform: numeric_state
        entity_id: sensor.child_age_months
        above: 23
    condition:
      - condition: state
        entity_id: input_select.child_sleep_mode
        state: toddler
    action:
      - service: input_boolean.turn_on
        target:
          entity_id: input_boolean.tog_transition_pending
      - service: notify.notify
        data:
          title: "Sleep Mode Update"
          message: >
            Your child is 2 years old. Switch to child mode for blanket and
            sleepwear recommendations without a sleep sack when ready.
          data:
            actions:
              - action: TOG_SWITCH_CHILD
                title: Switch to Child Mode
              - action: TOG_REMIND_LATER
                title: Remind me in a month
```

### Monthly Reminder

```yaml
  - id: tog_monthly_mode_reminder
    alias: TOG - Monthly Mode Transition Reminder
    mode: single
    trigger:
      - platform: time
        at: "09:00:00"
    condition:
      - condition: template
        value_template: "{{ now().day == 1 }}"
      - condition: state
        entity_id: input_boolean.tog_transition_pending
        state: "on"
    action:
      - service: notify.notify
        data:
          title: "Sleep Mode Reminder"
          message: >
            Reminder: your child is {{ states('sensor.child_age_months') }} months old.
            Ready to update their sleep mode?
```

### Notification Action Handlers

```yaml
  - id: tog_notification_action_switch_mode
    alias: TOG - Notification Action - Switch Mode
    mode: single
    trigger:
      - platform: event
        event_type: mobile_app_notification_action
        event_data:
          action: TOG_SWITCH_TODDLER
        id: switch_toddler
      - platform: event
        event_type: mobile_app_notification_action
        event_data:
          action: TOG_SWITCH_CHILD
        id: switch_child
    action:
      - choose:
          - conditions:
              - condition: template
                value_template: "{{ trigger.id == 'switch_toddler' }}"
            sequence:
              - service: input_select.select_option
                target:
                  entity_id: input_select.child_sleep_mode
                data:
                  option: toddler
          - conditions:
              - condition: template
                value_template: "{{ trigger.id == 'switch_child' }}"
            sequence:
              - service: input_select.select_option
                target:
                  entity_id: input_select.child_sleep_mode
                data:
                  option: child
      - service: input_boolean.turn_off
        target:
          entity_id: input_boolean.tog_transition_pending

  - id: tog_notification_action_remind_later
    alias: TOG - Notification Action - Remind Later
    mode: single
    trigger:
      - platform: event
        event_type: mobile_app_notification_action
        event_data:
          action: TOG_REMIND_LATER
    action:
      - service: system_log.write
        data:
          message: "TOG: remind-later tapped, will resurface on the 1st of next month."
          level: info
```

---

## Nightly Notification

```yaml
automation:
  - id: tog_bedtime_notification
    alias: TOG - Bedtime Sleep Recommendation
    mode: single
    trigger:
      - platform: time
        at: input_datetime.tog_bedtime_notification_time
    variables:
      headline: "{{ state_attr('sensor.childtog_night_recommendation', 'headline') }}"
      tog: "{{ states('sensor.childtog_night_tog') }}"
      effective_f: "{{ state_attr('sensor.childtog_night_recommendation', 'effective_temperature_f') }}"
      items: "{{ state_attr('sensor.childtog_night_recommendation', 'clothing_items') | join(', ') }}"
      message: "{{ headline }} ({{ tog }} TOG) -- {{ items }}. Effective {{ effective_f }}F."
    action:
      - service: notify.notify
        data:
          title: "Tonight's Sleep Setup"
          message: "{{ message }}"
```

---

## Dashboard Settings Card

The integration's mutable settings are controlled via helper entities, not the config flow. A companion entities card in your dashboard gives you a single panel to view and change all of them without opening Developer Tools.

Add this card to the child's room view alongside the TOG recommendation card:

```yaml
type: entities
title: TOG Settings
entities:
  - entity: input_select.child_sleep_mode
    name: Sleep Mode
  - entity: input_boolean.child_uses_sleep_sack
    name: Uses Sleep Sack
  - entity: input_number.tog_temp_offset
    name: Temperature Offset
  - type: divider
  - entity: input_datetime.tog_bedtime_notification_time
    name: Notification Time
  - entity: input_select.tog_notification_target
    name: Notify
  - type: divider
  - entity: input_datetime.child_birthday
    name: Birthday
  - entity: sensor.child_age_months
    name: Age (months)
```

### What Each Control Does

| Entity | Effect |
|---|---|
| `input_select.child_sleep_mode` | Switches the clothing recommendation table — `baby`, `toddler`, or `child`. Can be changed manually or set automatically by milestone automations. |
| `input_boolean.child_uses_sleep_sack` | When off and mode is `toddler`, switches to blanket/sheet language (toddler blanket mode). Has no effect in baby or child mode. |
| `input_number.tog_temp_offset` | Shifts all recommendations warmer (positive) or cooler (negative) by up to ±3°C. Use when the standard calculation consistently feels one tier off for your room. |
| `input_datetime.tog_bedtime_notification_time` | Time the nightly push notification fires. |
| `input_select.tog_notification_target` | Who receives milestone and nightly notifications — one parent, the other, or both. |
| `input_datetime.child_birthday` | Used to calculate current age in months. Feeds all milestone automations. |
| `sensor.child_age_months` | Read-only. Displays the child's current age in whole months, derived from birthday. |

Changes to any of these take effect on the next coordinator update (within 15 minutes, or immediately if the coordinator detects the helper change).

---

## Multiple Children

Each child needs their own set of helpers and their own integration instance.

### 1. Create helpers with distinct entity IDs

```yaml
input_select:
  child2_sleep_mode:
    name: Child 2 Sleep Mode
    options: [baby, toddler, child]
    initial: baby

input_boolean:
  child2_uses_sleep_sack:
    name: Child 2 Uses Sleep Sack
    initial: true

input_number:
  child2_tog_temp_offset:
    name: Child 2 TOG Temperature Offset
    min: -3.0
    max: 3.0
    step: 0.5
    initial: 0.0
    unit_of_measurement: "°C"
    mode: slider

input_datetime:
  child2_birthday:
    name: Child 2 Birthday
    has_date: true
    has_time: false
```

### 2. Allow multiple config entries

Edit `custom_components/tog_rating/manifest.json`:

```json
"single_config_entry": false
```

### 3. Add a new integration entry

**Settings > Devices & Services > TOG Rating > Add entry.** Use the optional entity selector fields to point to the new child's helpers.

### 4. Duplicate automations

Copy milestone and notification handler automations into a new package file. Update all entity IDs. Use distinct notification action tags to avoid cross-child conflicts:

```
Child 1: TOG_SWITCH_TODDLER, TOG_SWITCH_CHILD, TOG_REMIND_LATER
Child 2: TOG2_SWITCH_TODDLER, TOG2_SWITCH_CHILD, TOG2_REMIND_LATER
```

### 5. Add dashboard cards

The new instance creates sensors named after its instance title. Add cards for the new child using those entity IDs.

### 6. Reload

Reload helpers and automations via **Developer Tools > YAML**. Restart HA if you modified `manifest.json`.

---

## Sensor Attributes Reference

| Attribute | Type | Description |
|---|---|---|
| `headline` | string | Short summary (e.g., "Standard setup") |
| `tog_rating` | float | TOG value of the sleep sack or blanket layer |
| `clothing_items` | list | Recommended items in order (base layer first) |
| `general_message` | string | One-sentence explanation |
| `reasoning` | string | Full temperature blend calculation |
| `effective_temperature_c` | float | Adjusted temperature used for tier selection (°C) |
| `effective_temperature_f` | float | Adjusted temperature used for tier selection (°F) |
| `risk` | string | `warm`, `comfortable`, `cool`, or `cold` |
| `child_mode` | string | Active mode at time of calculation |
| `source_label` | string | Current conditions / Day forecast / Night forecast |
| `indoor_temperature_c/f` | float | Raw indoor sensor reading |
| `outdoor_temperature_c/f` | float | Raw outdoor reading |
| `outdoor_temperature_weight_percent` | int | % outdoor influence applied |
| `outdoor_temperature_source` | string | `weather` or `forecast` |
| `humidity_adjustment_c` | float | Net humidity adjustment applied |
| `indoor_humidity` | float | Indoor humidity % (if configured) |
| `outdoor_humidity` | float | Outdoor humidity % from weather entity |
| `wind_speed_kmh` | float | Wind speed used in calculation |
| `precipitation_probability` | int | Rain probability % from forecast |
| `condition` | string | Weather condition string |
| `forecast_time` | string | ISO timestamp of forecast period (if applicable) |

---

## Repository Structure

```
tog-rating/
├── custom_components/
│   └── tog_rating/
│       ├── __init__.py
│       ├── config_flow.py      # UI setup and options flow
│       ├── const.py            # Constants, entity IDs, defaults
│       ├── coordinator.py      # DataUpdateCoordinator — reads sensors, calls logic
│       ├── logic.py            # Core TOG calculation and clothing recommendation tables
│       ├── manifest.json
│       ├── sensor.py           # Sensor platform
│       ├── strings.json
│       └── translations/
├── assets/                     # Screenshots
├── brands/                     # HACS brand icon
└── hacs.json
```

---

## Acknowledgements

Original integration by [Anton2079](https://github.com/Anton2079). This fork extends the original with:

- Four sleep modes: baby, toddler, toddler-with-blanket, child
- Automatic base layer recommendations derived from temperature
- Toddler blanket mode (activates automatically when sleep sack toggle is off)
- Live helper entity reads — settings update without restarting HA
- Birthday-based milestone automations with monthly reminders
- Multi-child support via per-instance helper entity selectors in the config flow
