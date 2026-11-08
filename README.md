# Arena Bibliothek – Home Assistant

Liest das Benutzerkonto eines **Axiell-Arena**-Katalogs aus und zeigt Ausleihen,
Rückgabefristen und überfällige Medien in Home Assistant. Entwickelt gegen die
Stadtbibliothek Mönchengladbach (`moenchengladbach.arena.axiell.de`), funktioniert
aber mit jeder Arena-Instanz – die Basis-URL ist frei einstellbar.

Rein lesend: die Integration verlängert nichts und verändert nichts am Konto.

## Wie es funktioniert

Arena ist ein Liferay-Portal mit Apache-Wicket-Portlets. Die Integration meldet
sich wie ein Browser am Login-Portlet an und liest die Kontoseite
`/protected/my-account/overview`. Die komplette Ausleihtabelle steht dort im
server-gerenderten HTML – kein JavaScript, kein zweiter Request nötig.

Die Form-Action des Login-Formulars enthält eine sitzungsabhängige
Wicket-Interface-ID. Die wird bei jeder Anmeldung frisch von der Startseite
gelesen statt hart hinterlegt, sonst bricht das Login nach dem nächsten
Portal-Neustart. Die Sitzung wird wiederverwendet; läuft sie ab, meldet sich die
Integration automatisch neu an.

## Installation

### Über HACS

1. HACS öffnen, oben rechts das Dreipunktmenü, *Custom repositories*
2. `https://github.com/bentastic4711/arena-bibliothek-ha` eintragen, Kategorie *Integration*
3. „Arena Bibliothek" installieren, Home Assistant neu starten

### Von Hand

Ordner `custom_components/arena_bibliothek/` nach `<config>/custom_components/`
kopieren und Home Assistant neu starten.

### Einrichten

**Einstellungen → Geräte & Dienste → Integration hinzufügen → „Arena Bibliothek"**,
dann Basis-URL, Ausweisnummer und Passwort eintragen.

## Vorher testen

Ohne Home Assistant prüfen, ob Login und Parser durchlaufen:

```bash
pip install requests beautifulsoup4
python3 custom_components/arena_bibliothek/api.py \
  --base-url https://moenchengladbach.arena.axiell.de \
  --username DEINE_AUSWEISNUMMER \
  --password DEIN_PASSWORT
```

Ausgabe ist eine nach Rückgabedatum sortierte Liste. Kommt hier etwas Sinnvolles
raus, funktioniert auch die Integration.

## Entitäten

| Entität | Zustand | Attribute |
|---|---|---|
| `sensor.…_ausleihen` | Anzahl der Ausleihen | `loans` (alle Felder je Medium), `renewable_count`, `titles` |
| `sensor.…_nachste_ruckgabe` | frühestes Rückgabedatum (`device_class: date`) | `days_left`, `titles`, `all_renewable` |
| `sensor.…_tage_bis_ruckgabe` | Tage bis zur frühesten Rückgabe, negativ wenn überfällig | – |
| `sensor.…_uberfallig` | Anzahl überfälliger Medien | `titles` |
| `calendar.…_ruckgabefristen` | ganztägiger Eintrag je Rückgabedatum | Beschreibung listet die Titel |

Felder eines Eintrags in `loans`: `title`, `author`, `authors`, `media_type`,
`year`, `due_date` (JJJJ-MM-TT), `days_left`, `renewable`, `renewals_left`,
`overdue`, `branch`, `note`, `record_id`.

Abrufintervall: standardmäßig 6 Stunden, unter *Konfigurieren* änderbar. Bitte
nicht zu knapp wählen – die Bibliothek soll nicht unnötig belastet werden.

## Automationen

Drei Tage vorher erinnern, mit Titelliste:

```yaml
alias: Bibliothek – Rückgabe steht an
triggers:
  - trigger: numeric_state
    entity_id: sensor.bibliothek_12345_tage_bis_ruckgabe
    below: 4
actions:
  - action: notify.mobile_app_nothing_phone_3
    data:
      title: >
        Bibliothek: {{ state_attr('sensor.bibliothek_12345_nachste_ruckgabe', 'days_left') }} Tage
      message: >
        {% for t in state_attr('sensor.bibliothek_12345_nachste_ruckgabe', 'titles') %}
        – {{ t }}
        {% endfor %}
```

Sonntagabend eine Sprachansage, wenn etwas fällig wird und nicht mehr
verlängerbar ist:

```yaml
alias: Bibliothek – nicht verlängerbar, bald fällig
triggers:
  - trigger: time
    at: "19:00:00"
variables:
  kritisch: >
    {{ (state_attr('sensor.bibliothek_12345_ausleihen', 'loans') or [])
       | selectattr('days_left', 'lt', 7)
       | rejectattr('renewable')
       | list }}
conditions:
  - condition: template
    value_template: "{{ kritisch | count > 0 }}"
actions:
  - action: notify.alexa_media_wohnzimmer
    data:
      message: >
        Achtung: {{ kritisch | count }} Medien müssen zurück und lassen sich
        nicht mehr verlängern.
      data:
        type: announce
```

## Blueprint: Erinnerung vor der Rückgabe

`blueprints/automation/arena_bibliothek/rueckgabe_erinnerung.yaml` nach
`<config>/blueprints/automation/arena_bibliothek/` kopieren, dann unter
**Einstellungen → Automatisierungen → Blueprints** anlegen.

Einstellbar sind der Vorlauf in Tagen, die Uhrzeit der täglichen Prüfung und
ein Schalter, der nur noch meldet, was sich nicht mehr verlängern lässt. Die
Benachrichtigung wählst du frei; in ihr stehen `{{ titel }}`, `{{ nachricht }}`
und `{{ anzahl }}` zur Verfügung.

## Dashboard-Karte

`lovelace/ausleihen-karte.yaml` enthält eine Markdown-Karte, die alle Ausleihen
mit Icon je Medientyp, Rückgabedatum und Restlaufzeit auflistet – rot bei
überfällig, orange ab drei Tagen. Entity-ID im Kopf der Datei anpassen.

## Grenzen

- **Verlängern geht nicht.** Die Verlängern-Buttons laufen über Wicket-Ajax mit
  sitzungsgebundenen Komponenten-IDs. Nachbaubar, aber fehleranfällig und mit
  echten Nebenwirkungen auf dem Konto – deshalb bewusst draußen.
- Das Parsing hängt an den CSS-Klassen von Arena (`arena-renewal-table`,
  `arena-renewal-date-value`, `arena-record-title` …). Ein Theme-Update der
  Bibliothek kann es brechen; dann ist der Loans-Sensor leer, nicht falsch.
- Reservierungen und offene Gebühren sind noch nicht erfasst. Beide stehen auf
  derselben Kontoseite und wären eine überschaubare Erweiterung.
- Zugangsdaten liegen wie bei jeder Integration in der HA-Konfiguration und
  damit auch in jedem Backup.
