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
| `toddler_blanket` | 18–24 months | Auto-activates when mode is `toddler` and the Uses Sleep Sack toggle is off |
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

## Recommendation Methodology

### What is TOG?

TOG (Thermal Overall Grade) is a standardized measure of thermal resistance defined in British Standard BS 5736. In infant and toddler sleep products, it rates how well a sleep sack or duvet retains heat. A higher TOG traps more warmth; a lower TOG allows more heat to escape.

Common sleep sack TOG values and their intended use:

| TOG | Intended room temperature |
|---|---|
| 0.2–0.5 | ≥ 24°C (75°F) — warm rooms |
| 1.0 | 20–24°C (68–75°F) — typical room temperature |
| 2.5 | 16–20°C (61–68°F) — cool or cold rooms |
| 3.5 | < 16°C (61°F) — cold rooms (not used by this integration) |

### Safety Guidelines and Frameworks

The temperature thresholds and clothing recommendations in this integration are derived from published child sleep safety guidance:

- **The Lullaby Trust** (UK) — primary source for room-temperature-to-TOG mappings. Their guidance directly links room temperature bands to appropriate TOG ratings and layering.
- **NHS (UK)** — recommends keeping a baby's room between 16–20°C (61–68°F) and avoiding overheating as a SIDS risk factor.
- **AAP (American Academy of Pediatrics)** — advises against loose bedding for infants under 12 months; recommends sleep sacks as the safe alternative. Used to inform mode transitions at 12 and 24 months.
- **Gro Company TOG chart** — widely cited industry reference for matching TOG sack to room temperature, consistent with Lullaby Trust guidance.

The five temperature tiers in this integration closely follow The Lullaby Trust's recommended TOG bands. Note that the warm tier uses heavier base layer clothing (footed or fleece PJs) to achieve equivalent warmth in toddler and child modes rather than always stepping up to a heavier sleep sack:

| Effective Temp | Lullaby Trust guidance | This integration |
|---|---|---|
| ≥ 24°C (75°F) | 0.5 TOG or sheet only | Very Light — 0.2–0.5 TOG |
| 22–24°C (71–75°F) | 1.0 TOG | Light — 1.0 TOG |
| 20–22°C (68–71°F) | 1.0 TOG + light base layer | Balanced — 1.0 TOG |
| 17–20°C (63–68°F) | 2.5 TOG or warmer base layer | Warm — heavier base, 1.0–2.5 TOG |
| < 17°C (63°F) | 2.5 TOG + footed sleepsuit | Extra Warm — fleece/thermal + 2.5 TOG |

For toddlers and children no longer using a sleep sack, equivalent warmth is achieved by adjusting the pajama weight (short-sleeve → long-sleeve → footed → fleece) and blanket weight (sheet → thin → light → warm → heavy), following the same temperature band logic.

### Full Calculation Pipeline

Each recommendation is computed in five steps:

#### Step 1 — Temperature blend

```
effective_temp = (indoor_temp × indoor_weight) + (outdoor_temp × outdoor_weight)
```

Default weights: **90% indoor / 10% outdoor** for an HVAC-controlled home. The outdoor component acknowledges that outdoor temperature still influences room temperature through walls, windows, and HVAC cycling, even when the thermostat is active.

If any configured opening sensor (window or door) has been open for more than 60 minutes, outdoor weight increases to **35%** to reflect natural ventilation replacing HVAC-controlled air.

#### Step 2 — Humidity adjustment

Humidity affects perceived temperature because moisture changes the rate of heat transfer from the body and alters how the air feels against skin.

```
humidity_adj = (indoor_humidity - 50) × 0.06
             + (outdoor_humidity - 50) × 0.04 × outdoor_weight
```

The 50% baseline is neutral. Each percentage point above 50% adds 0.06°C (indoor) or a scaled outdoor contribution; each point below subtracts it.

Example: 70% indoor humidity → +1.2°C effective (humid air feels warmer). 30% humidity → -1.2°C (dry air feels cooler and the body loses heat faster).

#### Step 3 — Weather condition adjustments

Additional adjustments account for outdoor conditions that can affect how cool or drafty a room feels, particularly with any air infiltration or ventilation:

| Condition | Adjustment |
|---|---|
| Wet weather (rain, snow, drizzle, etc.) | −1.5°C |
| Windy condition from weather entity | −0.5°C |
| Wind speed 25–39 km/h | −1.0°C |
| Wind speed ≥ 40 km/h | −2.0°C |
| Rain probability ≥ 60% | −0.5°C |

Wind adjustments stack with the windy-condition flag. Wet weather and wind are independent adjustments.

#### Step 4 — Temperature offset

A user-configurable offset (±3°C, default 0) is added last, after all other adjustments. This shifts all five tier thresholds equally, allowing calibration if the recommendations consistently feel one tier too warm or too cold for a specific room or child.

```
adjusted = effective_temp + temp_offset
```

#### Step 5 — Tier selection and clothing lookup

The adjusted effective temperature is mapped to a tier:

| Adjusted effective temp | Tier |
|---|---|
| ≥ 24°C | very_light |
| 22–24°C | light |
| 20–22°C | balanced |
| 17–20°C | warm |
| < 17°C | extra_warm |

The tier is used as a key to look up mode-specific clothing from the table for the active sleep mode (baby, toddler, toddler_blanket, or child).

### Clothing Tables by Mode

#### Baby (0–12 months)

A cotton onesie base layer is always worn regardless of temperature. Warmth is adjusted entirely through the sleep sack TOG.

| Tier | TOG | Clothing |
|---|---|---|
| Very light | 0.2 | Short-sleeve cotton onesie + 0.2 TOG sack |
| Light | 0.5 | Short-sleeve cotton onesie + 0.5 TOG sack |
| Balanced | 1.0 | Light cotton onesie + 1.0 TOG sack |
| Warm | 2.5 | Light cotton onesie + 2.5 TOG sack |
| Extra warm | 2.5 | Light cotton onesie + footed sleepsuit + 2.5 TOG sack |

#### Toddler with sleep sack (12–24 months)

Base layer scales with temperature. TOG steps up only at the cold extreme.

| Tier | TOG | Clothing |
|---|---|---|
| Very light | 0.5 | Short-sleeve cotton PJs + 0.5 TOG sack (or skip sack) |
| Light | 1.0 | Light short-sleeve cotton PJs + 1.0 TOG sack |
| Balanced | 1.0 | Long-sleeve cotton/jersey PJs + 1.0 TOG sack |
| Warm | 1.0 | Footed cotton/jersey PJs + 1.0 TOG sack |
| Extra warm | 2.5 | Footed fleece PJs or thermal base + 2.5 TOG sack |

#### Toddler with blanket (18–24 months)

Activates when "Uses Sleep Sack" is off. TOG is not rated (blanket weight varies); warmth is adjusted through PJ weight and blanket selection.

| Tier | Clothing |
|---|---|
| Very light | Short-sleeve PJs + sheet only |
| Light | Short-sleeve PJs + thin blanket |
| Balanced | Long-sleeve PJs + light blanket |
| Warm | Footed PJs + warm blanket |
| Extra warm | Footed fleece PJs or thermal base + heavy blanket |

#### Child (24+ months)

No sleep sack. Warmth adjusted through PJ weight and blanket selection.

| Tier | Clothing |
|---|---|
| Very light | Cotton shorts and short-sleeve top + sheet only |
| Light | Light cotton long PJs + thin blanket |
| Balanced | Long-sleeve cotton/jersey PJs + light blanket |
| Warm | Flannel or footed PJs + warm blanket |
| Extra warm | Thermal base under fleece/flannel PJs + heavy blanket |

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
| Opening sensors | Window/door sensors — increases outdoor temperature influence when open for more than 60 minutes |
| Sleep mode entity | The `input_select` that controls which clothing table is active. Defaults to `input_select.child_sleep_mode`. Set to a different entity ID when running multiple instances so each child uses their own sleep mode selector. |
| Bedding type entity | The `input_boolean` that toggles between sleep sack and blanket/sheet language in toddler mode. Defaults to `input_boolean.child_uses_sleep_sack`. Set to a child-specific entity for multi-child setups. |
| Temperature offset entity | The `input_number` used to shift recommendations warmer or cooler. Defaults to `input_number.tog_temp_offset`. Set to a child-specific entity to calibrate each child independently. |

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

Replace `childtog` in the entity IDs below with the slug derived from your instance name. For an instance named "Nursery TOG", the slug is `nurserytog`. Verify exact entity IDs in **Developer Tools > States**.

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

Add this card to the child's room view alongside the TOG recommendation card. Update entity IDs to match your own helpers if you used different names.

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
├── assets/                     # Brand assets and images
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
