# BESS-Twin user research kit: 5 interviews, 5 timed sessions, one afternoon each

Use this to replace the hypotheses in section 10 of the design document with evidence. **Record only what people actually say and do.** If you have run fewer sessions than planned, report the real number.

## Who to talk to

| Group | Where to find them | Target |
|---|---|---|
| Student EV, drone or eBAJA team members who designed or chose a battery pack | your college SAE or drone club, eBAJA or Formula Bharat teams | 5–8 |
| Early-stage battery, drone or EV start-up engineers | LinkedIn, incubators, start-up battery meetups | 3–5 |
| Faculty teaching EV or battery courses | your department | 2 |

## Part 1: problem interview, 20 minutes (do not show the tool yet)

1. Tell me about the last time you chose a cell, a cooling method or a pack layout. What did you have to decide?
2. Which tools did you use? (spreadsheet, MATLAB, datasheets, vendor calculator, nothing) How many separate files?
3. What went wrong, or what did you find out too late? (overheating, sag, weight, cost, BMS trips)
4. How long did the decision take, from first idea to a design you trusted?
5. Did you ever build something that you later had to change? What did that cost in money and days?
6. How do you show a reviewer or a judge why you chose your design?
7. If a tool could do one thing for you here, what should it be?

Write down exact quotes. Count how many people describe the "separate spreadsheets, found out too late" problem without being prompted. **Decision rule: continue if at least 6 of 10 describe it.**

## Part 2: usability, 15 minutes, timed

Open `bess_dashboard.html` on its home page. Say only: "This checks a battery module design. Please think aloud." Then hand over these tasks one at a time and time each. Do not help.

| # | Task | Success when | Time |
|---|---|---|---|
| 0 | From the home page, say in one sentence what this tool does, then open the checker. | a correct one-sentence summary; the checker is open | |
| 1 | Find out whether the Baseline design survives the default mission at 25 °C. | they say it fails, stopped by the hot-cell limit | |
| 2 | Change design B so it meets all requirements. | the B pill shows ALL REQUIREMENTS MET | |
| 3 | What happens to your design on a 40 °C day? | they open the 40 °C curves or read R4 | |
| 4 | Which assumption is your design's hot-day result most sensitive to? | they change the coolant offset or the current factor | |
| 5 | Copy your design so the Python engine can run it. | the copy button was used | |

**Decision rule: continue if the median user reaches task 2 in under 15 minutes without help.**

Afterwards, ask: "What confused you? What would make you use this on your next project?"

## Part 3: willingness to pay, 5 minutes (Van Westendorp)

Describe a paid tier: cell and part library backed by datasheets, PDF design-review export, saved team projects, and calibration from your own bench data. Then ask, for a student team's licence per year and for a start-up seat per year:

1. At what price would it be so cheap that you would doubt the quality?
2. At what price would it be a bargain?
3. At what price would it start to feel expensive, but you would still consider it?
4. At what price would it be too expensive to consider?

Plot the four cumulative curves. The acceptable range lies between the crossing points. **Decision rule: proceed with a paid tier only if the range overlaps the hypothesis in section 10.4.**

## Results log (fill in, do not estimate)

| # | Date | Group | Problem described unprompted? | Task 0 / 1 / 2 / 3 / 4 / 5 time (min) | Help needed | Too cheap / bargain / expensive / too expensive (₹) | Best quote |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |

Summarise in two lines for the pitch: "N of M described the problem unprompted. The median time to a passing design was X minutes."
