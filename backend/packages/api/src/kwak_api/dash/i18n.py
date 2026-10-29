"""The Dash pages' strings (the one exception to `frontend/src/i18n/`, CLAUDE.md): `EN` and
`FR` hold the same keys, which a test checks. Amounts and months follow the language."""

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from kwak_core.budget import Month

type Language = Literal["en", "fr"]

EN: Mapping[str, str] = {
    "title": "Projection",
    "intro": (
        "Where the wealth could be in 1 to 40 years, from what it holds today, what the "
        "household saves each month and what each kind of holding may earn: a fan of outcomes "
        "rather than one line, since returns are uncertain."
    ),
    "scope": "Scope",
    "scope_household": "Household",
    "scope_mine": "Only mine",
    "scope_joint": "Joint",
    "horizon": "Horizon",
    "years": "{n} years",
    "euros": "Amounts",
    "euros_today": "Today's euros",
    "euros_current": "Current euros",
    "median": "Median",
    "band_25_75": "25–75% of outcomes",
    "band_10_90": "10–90% of outcomes",
    "net_worth": "Net worth",
    "caption": (
        "An estimate from the assumptions below, not a forecast and not advice. One outcome in "
        "five lies outside the 10–90% band, and the real spread is wider (see the limits). The "
        "median line is not one path: no single outcome follows it. Past returns do not "
        "guarantee future ones."
    ),
    "savings_measured": "Monthly savings: {amount}, the goals' capacity measured over {n} months.",
    "savings_set": "Monthly savings: {amount}, the goals' capacity set by hand.",
    "savings_short": (
        "Fewer than 12 months miss the year's irregular costs (taxes, insurance, holidays)."
    ),
    "savings_household": (
        "In this scope it is still the whole household's capacity, which may be too much."
    ),
    "engine": "{paths} outcomes, seed {seed}, engine version {version}.",
    "no_wealth": "No wealth line in this scope: enter the wealth first.",
    "no_allocation": (
        "No category to save into: add Savings accounts or Current accounts to the wealth."
    ),
    "not_signed_in": "Sign in to Kwak Finance to see this page.",
    "not_found": "No such page.",
    "ret_intro": (
        "What standard of living the household could keep once retired: the pensions entered "
        "under the charts, and what the wealth can pay each month, against the retirement "
        "spending."
    ),
    "ret_no_member": (
        "Enter your birth month, your retirement and your pension under the charts to see the "
        "household's retirement."
    ),
    "ret_horizon": "The horizon comes before the household retires: raise the horizon age.",
    "ret_left_out": "Left out, without a retirement entered: {names}.",
    "ret_scope": "The wealth counted is the household's lines you see.",
    "ret_living": (
        "From {month}, pensions of {pensions} and a sustainable withdrawal of {withdrawal} a "
        "month give {total} a month in 9 outcomes in 10 ({total_half} in half of them), for "
        "spending of {spending}: {covered} covered."
    ),
    "ret_living_none": (
        "From {month}, pensions of {pensions} a month, for spending of {spending}. In more "
        "than one outcome in ten the liquid wealth has already run out by then: nothing can be "
        "withdrawn from it."
    ),
    "ret_model": (
        "9 in 10 in the model, not a guarantee: the real chance is lower (see the limits)."
    ),
    "ret_later_pension": (
        "A pension starting after the household's retirement leaves the years before it to "
        "the wealth: the chance below counts them, the withdrawal does not."
    ),
    "ret_lasts": (
        "In {chance} of the outcomes, the plan runs to {month} (the youngest {age} years old) "
        "without the liquid wealth running out."
    ),
    "ret_runs_out": (
        "The liquid wealth runs out by age {ten} in 1 outcome in 10, by age {half} in half of them."
    ),
    "ret_runs_out_ten": (
        "The liquid wealth runs out by age {ten} in 1 outcome in 10; in half of them, not "
        "before {age}."
    ),
    "ret_never": "In 9 outcomes in 10, the liquid wealth does not run out before {age}.",
    "ret_shortfall_after": (
        "From then on, the spending would have to be cut, or financed otherwise (the home, family)."
    ),
    "ret_fan_title": "Net worth to the horizon",
    "ret_liquid": "Liquid wealth (median)",
    "ret_retires": "Household retires",
    "ret_pension_of": "{name}'s pension",
    "ret_income_title": "Monthly income once retired",
    "ret_pensions": "Pensions",
    "ret_withdrawal": "Sustainable withdrawal (9 in 10)",
    "ret_spending": "Retirement spending",
    "ret_income_axis": "A month, today's euros",
    "ret_disclaimer": (
        "An estimate from the assumptions and the pensions you entered, not a forecast and not "
        "advice. Pension estimates change with your career and with reforms: check yours on "
        "info-retraite.fr. Past returns do not guarantee future ones."
    ),
    "ret_inputs_title": "Inputs",
    "ret_input_member": (
        "{name}: born {birth}, stops working in {retirement} at {age} with earnings of "
        "{earnings} stopping then; a pension of {pension} from {pension_month}, at {pension_age}."
    ),
    "ret_input_spending": "Retirement spending: {amount} a month, {how}.",
    "ret_how_share": (
        "{share} of today's spending outside the loans ({base}, measured over {months} months)"
    ),
    "ret_how_amount": "set by hand",
    "ret_input_indexation": "Pensions follow inflation {rate} a year.",
    "ret_input_horizon": "Horizon: {month}, when the youngest is {age}.",
    "ret_limit_pensions": "Pensions as entered, never revised but by the indexation setting.",
    "ret_limit_tax": (
        "No tax on withdrawals: from a PEA, a CTO or an assurance vie, the gains part is taxed, "
        "often 5 to 15% of what is withdrawn after many years."
    ),
    "ret_limit_care": (
        "Long-term care not modelled: a nursing home costs about €2,000 to €2,500 a month "
        "after aid."
    ),
    "ret_limit_household": (
        "The household's composition is fixed: no death, separation nor inheritance. After a "
        "death the survivor keeps a reversion pension (about 54% of a base pension, "
        "means-tested, 60% of an Agirc-Arrco one) and spends about two thirds to three "
        "quarters of what a couple does."
    ),
    "ret_limit_home": "The home is never sold nor mortgaged.",
    "reach_title": "Reaching an amount",
    "amount": "Amount",
    "reach_month": "Month",
    "reach_year": "Year",
    "reach_chance": "In {chance} of the outcomes, net worth is at least {amount} in {month}.",
    "reach_dates": "Half of the outcomes have reached it once by {half}, nine tenths by {ninety}.",
    "not_within": "not within the horizon",
    "after_horizon": "{month} is after the horizon: lengthen it to see the chance then.",
    "amount_missing": "Enter an amount to see the chance of reaching it.",
    "chance_low": "less than 1%",
    "chance_high": "more than 99%",
    "shortfall": (
        "In {share} of the outcomes the liquid holdings run out: the net worth still counts the "
        "home and locked-in funds, but the spending would have to be borrowed."
    ),
    "amount_line": "Amount to reach: {amount}",
    "by_category_title": "By category, today and at the horizon",
    "by_category_note": (
        "Each category's own median: together they need not add up to the median net worth."
    ),
    "debts": "Debts",
    "shortfall_name": "Shortfall",
    "show_data": "Show the data",
    "col_month": "Month",
    "base": "Base",
    "whatifs_title": "What-ifs",
    "whatifs_intro": (
        "Change the savings, the inflation, a category's return or the allocation, for this "
        "visit only: nothing is saved. Every scenario uses the same draws."
    ),
    "whatif": "What-if {n}",
    "whatif_on": "Compare what-if {n}",
    "wi_savings": "Monthly savings (€)",
    "wi_inflation": "Inflation (% a year)",
    "wi_category": "Category",
    "wi_return": "Return (% a year)",
    "wi_volatility": "Volatility (%)",
    "wi_allocation": "Allocation of the savings (%)",
    "wi_allocation_hint": "Leave empty to keep the current one; the shares sum to 100.",
    "wi_invalid": "What-if {n} is not compared: {reason}.",
    "reason_allocation": "the shares of the allocation sum to 100%",
    "reason_assumption": (
        "a return is above −100% and at most +100%, a volatility from 0 to 200%, to 0.1%"
    ),
    "reason_inflation": "the inflation is from −5% to 20%, to 0.1%",
    "reason_savings": "the savings are an amount in euros",
    "compare_title": "Scenarios at the horizon, {month}",
    "col_scenario": "Scenario",
    "col_median": "Median",
    "col_chance": "Chance of {amount} in {month}",
    "assumptions_title": "Assumptions",
    "assumption_line": "{category}: {ret} a year ± {vol}, a median growth of {median} a year",
    "inflation_line": "Inflation: {rate} a year.",
    "allocation_line": "Savings go to: {shares}.",
    "assumptions_where": "The base uses the household's assumptions, set under the charts.",
    "changes_line": "What-if {n}: {changes}.",
    "change_savings": "savings of {amount} a month",
    "change_inflation": "inflation of {rate}",
    "change_assumption": "{category} at {ret} ± {vol}",
    "change_allocation": "allocation {shares}",
    "no_change": "no change",
    "limits_title": "Limits",
    "limit_independent": (
        "Categories are drawn independently, as if stocks, private equity and crypto never fell "
        "together: in a crash they do, so the fan is narrower than reality."
    ),
    "limit_crashes": (
        "Returns follow a lognormal law: no crash beyond it and no total loss (a failed "
        "platform or token)."
    ),
    "limit_inflation": "The inflation is fixed over the whole horizon.",
    "limit_shortfall": "The Shortfall is borrowed at a fixed 8% a year.",
    "limit_tax": (
        "Returns are after a low-cost fund's fees and before tax: the wealth is what the "
        "holdings would be worth, not what selling them would bring after tax on the gains."
    ),
    "limit_ceilings": (
        "Savings accounts' ceilings (€22,950 on a Livret A, €12,000 on an LDDS) are not modelled."
    ),
    # The cash-flow forecast (spec §4.14).
    "fct_intro": (
        "What the next twelve months of spending could look like, from the household's own "
        "history: the fixed expenses due are known, the rest is forecast by the method that "
        "erred least on the months already entered, with a band of likely values."
    ),
    "fct_not_enough": (
        "A forecast needs 12 complete months of spending; there are {n} so far. Open the demo "
        "from the account menu to try it."
    ),
    "fct_summary": (
        "From {first} to {last}, an income of {income}, spending of {spent} and savings of "
        "{saved} are expected, leaving a rest of {rest} (between {low} and {high} about 8 times "
        "in 10)."
    ),
    "fct_summary_no_band": (
        "From {first} to {last}, an income of {income}, spending of {spent} and savings of "
        "{saved} are expected, leaving a rest of {rest} (too short a history for a range)."
    ),
    "fct_now": "{entered} spent so far in {month}, {expected} expected for the month.",
    "fct_now_above": (
        "{entered} spent so far in {month}: already above what was expected ({high} at most, "
        "about 8 times in 10)."
    ),
    "fct_months_title": "Month by month",
    "fct_income": "Income",
    "fct_spent": "Spent",
    "fct_spent_fixed": "Of which fixed expenses",
    "fct_saved": "Saved",
    "fct_rest": "Rest",
    "fct_band": "{name}, about 8 times in 10",
    "fct_forecast_of": "{name} (forecast)",
    "fct_origin": "Last complete month",
    "fct_axis": "A month",
    "fct_widened": "From {month}, the band is the last one measured on enough months, widened.",
    "fct_no_band": "No band yet: too few months to measure the errors.",
    "fct_targets_title": "Against the targets",
    "fct_targets_intro": (
        "{month}: each expense category with a target, its forecast and the chance of going "
        "over it, the likeliest overrun first."
    ),
    "fct_no_target": "No expense category has a target this month.",
    "fct_likely_over": "▲ likely over",
    "fct_may_go_over": "△ may go over",
    "fct_within": "✓ within",
    "fct_likely_short": "▲ likely short",
    "fct_may_fall_short": "△ may fall short",
    "fct_on_track": "✓ on track",
    "fct_year_title": "The year {year}",
    "fct_year_intro": (
        "Each target's or savings objective's amount to date (to {origin}) plus its forecast "
        "to December, against the full year's."
    ),
    "fct_savings_title": "Savings objectives",
    "fct_savings_intro": "{month}: each savings category with an objective, and the chance of "
    "saving less.",
    "fct_income_title": "Income",
    "fct_rests_title": "What the forecast rests on",
    "fct_rests_intro": (
        "For each category, the method that erred least when it forecast the months already "
        "entered (its MASE: below 1, it errs less than repeating the previous month), against "
        "the 6-month average, and how often the months entered fell inside the band built from "
        "the errors known at the time (8 times in 10 expected)."
    ),
    "fct_m_baseline": "the average of the last 6 months",
    "fct_m_average_3": "the average of the last 3 months",
    "fct_m_average_12": "the average of the last 12 months",
    "fct_m_average_all": "the average of the whole history",
    "fct_m_naive": "the last month",
    "fct_m_seasonal_naive": "the same month last year",
    "fct_m_ses": "exponential smoothing, weighing the last months most",
    "fct_m_ets": "an exponential smoothing chosen automatically (ETS)",
    "fct_m_theta": "the Theta method",
    "fct_m_arima": "an ARIMA model chosen automatically",
    "fct_m_adida": "ADIDA, for months often empty",
    "fct_m_trees": "trees learnt on all the categories",
    "fct_m_none": "no line yet: its fixed expenses due only",
    "fct_no_contest": "{method} (kept without a contest: too few months, or always the same)",
    "fct_better": "errs {share} less",
    "fct_same": "the baseline",
    "fct_mostly": "{method}, mostly from {features}",
    "fct_f_lag1": "the last month",
    "fct_f_lag2": "2 months before",
    "fct_f_lag3": "3 months before",
    "fct_f_lag6": "6 months before",
    "fct_f_lag12": "the same month last year",
    "fct_f_mean3": "the 3-month average",
    "fct_f_mean6": "the 6-month average",
    "fct_f_month": "the calendar month",
    "fct_f_category": "the category",
    "fct_backtest_title": "The back-test",
    "fct_backtest_intro": (
        "At each month of the history, the totals forecast one month ahead from the months "
        "before it only, against what was entered."
    ),
    "fct_entered": "{name}: entered",
    "fct_one_ahead": "{name}: forecast one month ahead",
    "col_category": "Category",
    "col_forecast": "Forecast",
    "col_band": "About 8 times in 10",
    "col_target": "Target",
    "col_objective": "Objective",
    "col_odds": "Chance",
    "col_status": "Status",
    "col_to_date": "To date",
    "col_to_december": "Forecast to December",
    "col_year": "The year",
    "col_year_target": "Full-year target",
    "col_method": "Method",
    "col_known": "Fixed expenses due (12 months)",
    "col_mase": "MASE",
    "col_wape": "WAPE",
    "col_rmsse": "RMSSE",
    "col_vs_baseline": "Against the 6-month average",
    "col_coverage": "Inside the band",
    "col_total": "Total",
    "col_entered": "Entered",
    "col_one_ahead": "Forecast one month ahead",
    "fct_range": "{low} – {high}",
    "fct_rare": "rare in the past months",
    "fct_nearly": "nearly always in the past months",
    "fct_disclaimer": (
        "An estimate drawn from your past months: not a prediction of your decisions, and not "
        "advice. A new expense, a change of job or a move are not in the history: the band "
        "reflects only the past months' surprises, and holds about 8 times in 10 if the coming "
        "months resemble them."
    ),
    "fct_limit_fixed": (
        "A fixed expense counts at its current amount: an estimated bill may differ."
    ),
    "fct_limit_bands": (
        "The bands rest on the back-tests that chose the methods, so they may be narrow: the "
        "coverage measured above shows how often they held."
    ),
    "fct_limit_yearly": (
        "Under 24 months of history, a sum that comes once a year (a 13th month, a bonus, an "
        "annual tax or insurance) is forecast only if it is a fixed expense; otherwise it is "
        "spread over the months."
    ),
    "fct_limit_euros": "Amounts in current euros, not deflated.",
    "fct_limit_change": (
        "A change in the past months (a raise, a benefit that ended) shows in the errors: the "
        "band may then lean to one side, as the past surprises did."
    ),
    "fct_engine": (
        "{cuts} back-test cuts over {n} months of history, seed {seed}, engine version {version}."
    ),
    "fct_m_chronos_2": (
        "Chronos-2, a model pretrained on many public series, from this category's months alone"
    ),
    "fct_m_timesfm": (
        "TimesFM 2.5, a model pretrained on many public series, from this category's months alone"
    ),
    "fct_name_chronos_2": "Chronos-2",
    "fct_name_timesfm": "TimesFM 2.5",
    "fct_bias_expense_less": "{share} less spending than was entered",
    "fct_bias_expense_more": "{share} more spending than was entered",
    "fct_bias_income_less": "{share} less income than was received",
    "fct_bias_income_more": "{share} more income than was received",
    "fct_bias_savings_less": "{share} less savings than was saved",
    "fct_bias_savings_more": "{share} more savings than was saved",
    "fct_bias_none": "about what was entered",
    "fct_bias_rest_above": "the rest {amount} a month above what was left",
    "fct_bias_rest_below": "the rest {amount} a month below what was left",
    "fct_set_aside": (
        "{model} erred {share} less but forecast {bias} in the past months tested, so it was not "
        "used."
    ),
    "fct_rest_warning": (
        "In the past months tested, this forecast put the rest {amount} a month above what was "
        "left: the rest may be lower than shown."
    ),
    "col_bias": "Bias, past months tested",
    "fct_limit_prices": (
        "A price rise faster than in the past months is forecast late: in such a period, the "
        "spending forecast may be low."
    ),
    "fct_models": "Foundation models: {models}.",
    "fct_no_models": "Foundation models not installed (see Running Kwak Finance).",
    "fct_jump_month": "This month",
    "fct_jump_months": "12 months",
    "fct_jump_targets": "Targets",
    "fct_jump_year": "The year",
    "fct_jump_reliable": "How reliable",
    "fct_tile_rest": "Rest, {first} to {last}",
    "fct_tile_month": "{month} so far",
    "fct_tile_targets": "Targets this month",
    "fct_tile_year": "Targets in {year}",
    "fct_tile_income": "Income, 12 months",
    "fct_tile_spent": "Spending, 12 months",
    "fct_tile_saved": "Savings, 12 months",
    "fct_per_month": "about {amount} a month",
    "fct_count_over": "{n} likely over",
    "fct_count_watch": "{n} may go over",
    "fct_all_within": "all within",
    "fct_at_risk": "{n} at risk of {of}",
    "fct_months_lede": (
        "What comes in, what goes out and what is left each month; dashed, the months to come, "
        "their bands holding about 8 times in 10."
    ),
    "fct_rest_of_month": "Rest of the month",
    "fct_targets_lede": (
        "Each category in percent of its target: the point is the forecast, the bar its band, "
        "the line the target."
    ),
    "fct_year_lede": (
        "Solid, the year to date; lighter, the forecast to December; the thin line, the band of"
        " the year's total; in percent of the full-year target."
    ),
    "fct_to_origin": "To {month}",
    "fct_income_lede": "{month}: each income category's forecast and its band.",
    "fct_objective_chip": "{name}: {point} for {target}, {word}",
    "fct_reliable_title": "How reliable it is",
    "fct_reliable_hint": (
        "the methods, the back-test and the limits: to check, not to read every day"
    ),
    "fct_gain_axis": "Errs less than the 6-month average",
    "fct_bias_axis": "Optimistic to the right",
    "ret_jump_life": "Timeline",
    "ret_jump_income": "Income",
    "ret_jump_fan": "Net worth",
    "ret_jump_inputs": "Inputs",
    "ret_tile_living": "Standard of living from {month}, 9 in 10",
    "ret_per_month": "{amount} a month",
    "ret_split_pensions": "Pensions {amount}",
    "ret_split_withdrawal": "Withdrawal {amount}",
    "ret_against": "Spending {amount}",
    "ret_tile_covered": "Spending covered",
    "ret_covered": "covered",
    "ret_short": "short",
    "ret_tile_lasts": "The wealth lasts to the horizon",
    "ret_life_title": "Timeline",
    "ret_life_lede": "Who works, who draws a pension, and how far the plan is tested.",
    "ret_working": "Works, {amount}",
    "ret_pension_segment": "Pension {amount}",
    "ret_today": "Today",
    "ret_retires_at": "{name} retires at {age}",
    "ret_horizon_at": "Horizon: {name} at {age}",
    "ret_income_lede": (
        "The pensions plus the sustainable withdrawal (9 in 10), against the retirement spending."
    ),
    "ret_fan_lede": (
        "Net worth, its median and its range, and the liquid part that pays the withdrawal."
    ),
    "ret_limits_hint": "taxes, long-term care, a death: what the model leaves out",
    "jump_fan": "Trajectory",
    "jump_reach": "An amount",
    "jump_mix": "By category",
    "jump_whatifs": "What-ifs",
    "jump_assumptions": "Assumptions",
    "fan_title": "Net worth over the horizon",
    "fan_lede": (
        "The median and the range of the outcomes; on the amount's line, when half and nine "
        "tenths of them have reached it."
    ),
    "reach_marks": "Reached by half, nine tenths",
    "today_bars": "Today",
    "return_axis": "Expected return a year, ± its volatility",
    "limits_hint": "what the model leaves out",
    "tile_today": "Net worth today",
    "tile_savings": "{amount} saved a month",
    "tile_median": "Median in {month}",
    "tile_range": "between {low} and {high} 8 times in 10",
    "tile_amount": "{amount} in {month}",
    "tile_half": "half the outcomes reach it by {month}",
}

FR: Mapping[str, str] = {
    "title": "Projection",
    "intro": (
        "Où pourrait en être le patrimoine dans 1 à 40 ans, d'après ce qu'il contient "
        "aujourd'hui, ce que le foyer épargne chaque mois et ce que chaque type de placement "
        "peut rapporter : un éventail de résultats plutôt qu'une ligne, car les rendements sont "
        "incertains."
    ),
    "scope": "Périmètre",
    "scope_household": "Foyer",
    "scope_mine": "Seulement les miens",
    "scope_joint": "En commun",
    "horizon": "Horizon",
    "years": "{n} ans",
    "euros": "Montants",
    "euros_today": "Euros d'aujourd'hui",
    "euros_current": "Euros courants",
    "median": "Médiane",
    "band_25_75": "25–75\u202f% des résultats",
    "band_10_90": "10–90\u202f% des résultats",
    "net_worth": "Patrimoine net",
    "caption": (
        "Une estimation tirée des hypothèses ci-dessous, ni une prévision ni un conseil. Un "
        "résultat sur cinq sort de la bande 10–90\u202f%, et l'écart réel est plus large (voir les "
        "limites). La médiane n'est pas un chemin : aucun résultat ne la suit. Les rendements "
        "passés ne présagent pas des rendements futurs."
    ),
    "savings_measured": (
        "Épargne mensuelle : {amount}, la capacité des objectifs mesurée sur {n} mois."
    ),
    "savings_set": "Épargne mensuelle : {amount}, la capacité des objectifs saisie à la main.",
    "savings_short": (
        "Moins de 12 mois oublient les dépenses irrégulières de l'année (impôts, assurances, "
        "vacances)."
    ),
    "savings_household": (
        "Dans ce périmètre, c'est toujours la capacité de tout le foyer, peut-être trop élevée."
    ),
    "engine": "{paths} résultats, graine {seed}, version du moteur {version}.",
    "no_wealth": "Aucune ligne de patrimoine dans ce périmètre : saisissez d'abord le patrimoine.",
    "no_allocation": (
        "Aucune catégorie où épargner : ajoutez des Livrets ou des Comptes courants au patrimoine."
    ),
    "not_signed_in": "Connectez-vous à Kwak Finance pour voir cette page.",
    "not_found": "Cette page n'existe pas.",
    "ret_intro": (
        "Le niveau de vie que le foyer pourrait garder une fois retraité : les pensions saisies "
        "sous les graphiques, et ce que le patrimoine peut verser chaque mois, face aux "
        "dépenses de retraite."
    ),
    "ret_no_member": (
        "Saisissez votre mois de naissance, votre départ et votre pension sous les graphiques "
        "pour voir la retraite du foyer."
    ),
    "ret_horizon": "L'horizon arrive avant la retraite du foyer : relevez l'âge de l'horizon.",
    "ret_left_out": "Non compté, sans retraite saisie : {names}.",
    "ret_scope": "Le patrimoine compté est celui des lignes du foyer que vous voyez.",
    "ret_living": (
        "À partir de {month}, des pensions de {pensions} et un retrait soutenable de "
        "{withdrawal} par mois donnent {total} par mois dans 9 cas sur 10 ({total_half} dans "
        "la moitié des cas), pour des dépenses de {spending}, couvertes à {covered}."
    ),
    "ret_living_none": (
        "À partir de {month}, des pensions de {pensions} par mois, pour des dépenses de "
        "{spending}. Dans plus d'un cas sur dix, le patrimoine liquide est déjà épuisé : rien "
        "ne peut en être retiré."
    ),
    "ret_model": (
        "9 sur 10 dans le modèle, pas une garantie : la chance réelle est plus faible (voir les "
        "limites)."
    ),
    "ret_later_pension": (
        "Une pension qui démarre après la retraite du foyer laisse les années d'avant au "
        "patrimoine : la chance ci-dessous les compte, le retrait non."
    ),
    "ret_lasts": (
        "Dans {chance} des résultats, le plan tient jusqu'en {month} (le plus jeune a {age} "
        "ans) sans que le patrimoine liquide s'épuise."
    ),
    "ret_runs_out": (
        "Le patrimoine liquide s'épuise vers {ten} ans dans 1 cas sur 10, vers {half} ans dans "
        "la moitié des cas."
    ),
    "ret_runs_out_ten": (
        "Le patrimoine liquide s'épuise vers {ten} ans dans 1 cas sur 10 ; dans la moitié des "
        "cas, pas avant {age} ans."
    ),
    "ret_never": "Dans 9 cas sur 10, le patrimoine liquide ne s'épuise pas avant {age} ans.",
    "ret_shortfall_after": (
        "Dès lors, il faudrait réduire les dépenses ou les financer autrement (le logement, la "
        "famille)."
    ),
    "ret_fan_title": "Le patrimoine net jusqu'à l'horizon",
    "ret_liquid": "Patrimoine liquide (médiane)",
    "ret_retires": "Retraite du foyer",
    "ret_pension_of": "Pension de {name}",
    "ret_income_title": "Les revenus mensuels une fois retraité",
    "ret_pensions": "Pensions",
    "ret_withdrawal": "Retrait soutenable (9 sur 10)",
    "ret_spending": "Dépenses de retraite",
    "ret_income_axis": "Par mois, en euros d'aujourd'hui",
    "ret_disclaimer": (
        "Une estimation tirée des hypothèses et des pensions saisies, ni une prévision ni un "
        "conseil. Les estimations de pension changent avec la carrière et les réformes : "
        "vérifiez la vôtre sur info-retraite.fr. Les rendements passés ne présagent pas des "
        "rendements futurs."
    ),
    "ret_inputs_title": "Données utilisées",
    "ret_input_member": (
        "{name} : né(e) en {birth}, arrête de travailler en {retirement} à {age} ans avec un "
        "revenu de {earnings} qui s'arrête alors ; une pension de {pension} à partir de "
        "{pension_month}, à {pension_age} ans."
    ),
    "ret_input_spending": "Dépenses de retraite : {amount} par mois, {how}.",
    "ret_how_share": (
        "{share} des dépenses d'aujourd'hui hors prêts ({base}, mesurées sur {months} mois)"
    ),
    "ret_how_amount": "saisies à la main",
    "ret_input_indexation": "Les pensions suivent l'inflation {rate} par an.",
    "ret_input_horizon": "Horizon : {month}, quand le plus jeune a {age} ans.",
    "ret_limit_pensions": (
        "Pensions telles que saisies, jamais révisées sauf par le réglage d'indexation."
    ),
    "ret_limit_tax": (
        "Pas d'impôt sur les retraits : d'un PEA, d'un CTO ou d'une assurance vie, la part de "
        "plus-value est imposée, souvent 5 à 15 % de ce qui est retiré après de longues "
        "années."
    ),
    "ret_limit_care": (
        "La dépendance n'est pas modélisée : un Ehpad coûte environ 2 000 à 2 500 € "
        "par mois après aides."
    ),
    "ret_limit_household": (
        "La composition du foyer est fixe : ni décès, ni séparation, ni héritage. Après un "
        "décès, le survivant garde une pension de réversion (environ 54 % d'une pension "
        "de base, sous conditions de ressources, 60 % d'une pension Agirc-Arrco) et "
        "dépense environ les deux tiers à trois quarts de ce que dépense un couple."
    ),
    "ret_limit_home": "Le logement n'est jamais vendu ni hypothéqué.",
    "reach_title": "Atteindre un montant",
    "amount": "Montant",
    "reach_month": "Mois",
    "reach_year": "Année",
    "reach_chance": (
        "Dans {chance} des résultats, le patrimoine net atteint au moins {amount} en {month}."
    ),
    "reach_dates": (
        "La moitié des résultats l'ont atteint une fois en {half}, neuf sur dix en {ninety}."
    ),
    "not_within": "pas dans l'horizon",
    "after_horizon": "{month} est après l'horizon : allongez-le pour voir la chance à ce mois.",
    "amount_missing": "Saisissez un montant pour voir la chance de l'atteindre.",
    "chance_low": "moins de 1\u202f%",
    "chance_high": "plus de 99\u202f%",
    "shortfall": (
        "Dans {share} des résultats, les avoirs liquides s'épuisent : le patrimoine net compte "
        "encore le logement et les fonds bloqués, mais les dépenses devraient être empruntées."
    ),
    "amount_line": "Montant à atteindre : {amount}",
    "by_category_title": "Par catégorie, aujourd'hui et à l'horizon",
    "by_category_note": (
        "La médiane propre à chaque catégorie : ensemble, elles ne font pas forcément la médiane "
        "du patrimoine net."
    ),
    "debts": "Dettes",
    "shortfall_name": "Découvert",
    "show_data": "Afficher les données",
    "col_month": "Mois",
    "base": "Base",
    "whatifs_title": "Et si",
    "whatifs_intro": (
        "Changez l'épargne, l'inflation, le rendement d'une catégorie ou l'allocation, pour "
        "cette visite seulement : rien n'est enregistré. Chaque scénario utilise les mêmes "
        "tirages."
    ),
    "whatif": "Et si {n}",
    "whatif_on": "Comparer l'« et si » {n}",
    "wi_savings": "Épargne mensuelle (€)",
    "wi_inflation": "Inflation (% par an)",
    "wi_category": "Catégorie",
    "wi_return": "Rendement (% par an)",
    "wi_volatility": "Volatilité (%)",
    "wi_allocation": "Allocation de l'épargne (%)",
    "wi_allocation_hint": "Laissez vide pour garder l'actuelle ; les parts font 100 au total.",
    "wi_invalid": "L'« et si » {n} n'est pas comparé : {reason}.",
    "reason_allocation": "les parts de l'allocation font 100\u202f% au total",
    "reason_assumption": (
        "un rendement est au-dessus de −100\u202f% et au plus de +100\u202f%, "
        "une volatilité de 0 à 200\u202f%, à 0,1\u202f% près"
    ),
    "reason_inflation": "l'inflation va de −5\u202f% à 20\u202f%, à 0,1\u202f% près",
    "reason_savings": "l'épargne est un montant en euros",
    "compare_title": "Les scénarios à l'horizon, {month}",
    "col_scenario": "Scénario",
    "col_median": "Médiane",
    "col_chance": "Chance de {amount} en {month}",
    "assumptions_title": "Hypothèses",
    "assumption_line": (
        "{category} : {ret} par an ± {vol}, une croissance médiane de {median} par an"
    ),
    "inflation_line": "Inflation : {rate} par an.",
    "allocation_line": "L'épargne va à : {shares}.",
    "assumptions_where": "La base utilise les hypothèses du foyer, réglées sous les graphiques.",
    "changes_line": "Et si {n} : {changes}.",
    "change_savings": "épargne de {amount} par mois",
    "change_inflation": "inflation de {rate}",
    "change_assumption": "{category} à {ret} ± {vol}",
    "change_allocation": "allocation {shares}",
    "no_change": "aucun changement",
    "limits_title": "Limites",
    "limit_independent": (
        "Les catégories sont tirées indépendamment, comme si actions, private equity et crypto "
        "ne chutaient jamais ensemble : dans un krach, elles le font, l'éventail est donc plus "
        "étroit que la réalité."
    ),
    "limit_crashes": (
        "Les rendements suivent une loi lognormale : pas de krach au-delà, ni de perte totale "
        "(une plateforme ou un jeton qui fait faillite)."
    ),
    "limit_inflation": "L'inflation est fixe sur tout l'horizon.",
    "limit_shortfall": "Le découvert est emprunté à 8\u202f% par an, fixe.",
    "limit_tax": (
        "Les rendements sont après les frais d'un fonds peu cher et avant impôts : le patrimoine "
        "est ce que vaudraient les avoirs, pas ce que leur vente rapporterait après l'impôt sur "
        "les plus-values."
    ),
    "limit_ceilings": (
        "Les plafonds des livrets (22 950 € pour un Livret A, 12 000 € pour un LDDS) ne sont pas "
        "modélisés."
    ),
    # La prévision de trésorerie (spec §4.14).
    "fct_intro": (
        "À quoi pourraient ressembler les douze prochains mois, d'après l'historique du foyer : "
        "les dépenses fixes à venir sont connues, le reste est prévu par la méthode qui s'est le "
        "moins trompée sur les mois déjà saisis, avec une fourchette de valeurs probables."
    ),
    "fct_not_enough": (
        "Une prévision demande 12 mois complets de dépenses ; il y en a {n} pour l'instant. "
        "Ouvrez la démo depuis le menu du compte pour l'essayer."
    ),
    "fct_summary": (
        "Entre {first} et {last}, des revenus de {income}, des dépenses de {spent} et une "
        "épargne de {saved} sont attendus, soit un reste de {rest} (entre {low} et {high} "
        "environ 8 fois sur 10)."
    ),
    "fct_summary_no_band": (
        "Entre {first} et {last}, des revenus de {income}, des dépenses de {spent} et une "
        "épargne de {saved} sont attendus, soit un reste de {rest} (historique trop court pour une "
        "fourchette)."
    ),
    "fct_now": "{entered} dépensés en {month} jusqu'ici, {expected} attendus sur le mois.",
    "fct_now_above": (
        "{entered} dépensés en {month} jusqu'ici : déjà au-dessus de ce qui était attendu "
        "({high} au plus, environ 8 fois sur 10)."
    ),
    "fct_months_title": "Mois par mois",
    "fct_income": "Revenus",
    "fct_spent": "Dépensé",
    "fct_spent_fixed": "Dont dépenses fixes",
    "fct_saved": "Épargné",
    "fct_rest": "Reste",
    "fct_band": "{name}, environ 8 fois sur 10",
    "fct_forecast_of": "{name} (prévision)",
    "fct_origin": "Dernier mois complet",
    "fct_axis": "Par mois",
    "fct_widened": (
        "À partir de {month}, la fourchette est la dernière mesurée sur assez de mois, élargie."
    ),
    "fct_no_band": "Pas encore de fourchette : trop peu de mois pour mesurer les erreurs.",
    "fct_targets_title": "Face aux objectifs",
    "fct_targets_intro": (
        "{month} : chaque catégorie de dépense avec un objectif, sa prévision et la probabilité "
        "de le dépasser, le dépassement le plus probable en premier."
    ),
    "fct_no_target": "Aucune catégorie de dépense n'a d'objectif ce mois-ci.",
    "fct_likely_over": "▲ dépassement probable",
    "fct_may_go_over": "△ dépassement possible",
    "fct_within": "✓ dans l'objectif",
    "fct_likely_short": "▲ manque probable",
    "fct_may_fall_short": "△ manque possible",
    "fct_on_track": "✓ en bonne voie",
    "fct_year_title": "L'année {year}",
    "fct_year_intro": (
        "Le montant à date de chaque objectif de dépense ou d'épargne (jusqu'à {origin}) plus "
        "sa prévision jusqu'en décembre, face à celui de l'année entière."
    ),
    "fct_savings_title": "Objectifs d'épargne",
    "fct_savings_intro": "{month} : chaque catégorie d'épargne avec un objectif, et la "
    "probabilité d'épargner moins.",
    "fct_income_title": "Revenus",
    "fct_rests_title": "Sur quoi repose la prévision",
    "fct_rests_intro": (
        "Pour chaque catégorie, la méthode qui s'est le moins trompée en prévoyant les mois déjà "
        "saisis (son MASE : sous 1, elle se trompe moins que de répéter le mois précédent), "
        "face à la moyenne des 6 derniers mois, et la part des mois saisis tombés dans la "
        "fourchette construite avec les erreurs connues à l'époque (8 fois sur 10 attendu)."
    ),
    "fct_m_baseline": "la moyenne des 6 derniers mois",
    "fct_m_average_3": "la moyenne des 3 derniers mois",
    "fct_m_average_12": "la moyenne des 12 derniers mois",
    "fct_m_average_all": "la moyenne de tout l'historique",
    "fct_m_naive": "le dernier mois",
    "fct_m_seasonal_naive": "le même mois l'an dernier",
    "fct_m_ses": "un lissage exponentiel, qui pèse surtout les derniers mois",
    "fct_m_ets": "un lissage exponentiel choisi automatiquement (ETS)",
    "fct_m_theta": "la méthode Theta",
    "fct_m_arima": "un modèle ARIMA choisi automatiquement",
    "fct_m_adida": "ADIDA, pour des mois souvent vides",
    "fct_m_trees": "des arbres appris sur toutes les catégories",
    "fct_m_none": "aucune ligne encore : ses seules dépenses fixes à venir",
    "fct_no_contest": "{method} (gardée sans comparaison : trop peu de mois, ou toujours pareil)",
    "fct_better": "se trompe de {share} en moins",
    "fct_same": "la référence",
    "fct_mostly": "{method}, surtout d'après {features}",
    "fct_f_lag1": "le dernier mois",
    "fct_f_lag2": "il y a 2 mois",
    "fct_f_lag3": "il y a 3 mois",
    "fct_f_lag6": "il y a 6 mois",
    "fct_f_lag12": "le même mois l'an dernier",
    "fct_f_mean3": "la moyenne sur 3 mois",
    "fct_f_mean6": "la moyenne sur 6 mois",
    "fct_f_month": "le mois de l'année",
    "fct_f_category": "la catégorie",
    "fct_backtest_title": "Le back-test",
    "fct_backtest_intro": (
        "À chaque mois de l'historique, les totaux prévus un mois à l'avance à partir des seuls "
        "mois d'avant, face à ce qui a été saisi."
    ),
    "fct_entered": "{name} : saisi",
    "fct_one_ahead": "{name} : prévu un mois à l'avance",
    "col_category": "Catégorie",
    "col_forecast": "Prévision",
    "col_band": "Environ 8 fois sur 10",
    "col_target": "Objectif",
    "col_objective": "Objectif",
    "col_odds": "Probabilité",
    "col_status": "Statut",
    "col_to_date": "À date",
    "col_to_december": "Prévision jusqu'en décembre",
    "col_year": "L'année",
    "col_year_target": "Objectif de l'année",
    "col_method": "Méthode",
    "col_known": "Dépenses fixes à venir (12 mois)",
    "col_mase": "MASE",
    "col_wape": "WAPE",
    "col_rmsse": "RMSSE",
    "col_vs_baseline": "Face à la moyenne sur 6 mois",
    "col_coverage": "Dans la fourchette",
    "col_total": "Total",
    "col_entered": "Saisi",
    "col_one_ahead": "Prévu un mois à l'avance",
    "fct_range": "{low} – {high}",
    "fct_rare": "rare sur les mois passés",
    "fct_nearly": "presque toujours sur les mois passés",
    "fct_disclaimer": (
        "Une estimation tirée de vos mois passés : pas une prédiction de vos décisions, ni un "
        "conseil. Une nouvelle dépense, un changement d'emploi ou un déménagement ne sont pas "
        "dans l'historique : la fourchette ne reflète que les surprises des mois passés, et tient "
        "environ 8 fois sur 10 si les mois à venir leur ressemblent."
    ),
    "fct_limit_fixed": (
        "Une dépense fixe compte pour son montant actuel : une facture estimée peut différer."
    ),
    "fct_limit_bands": (
        "Les fourchettes reposent sur les back-tests qui ont choisi les méthodes, elles peuvent "
        "donc être étroites : la couverture mesurée plus haut montre combien de fois elles ont "
        "tenu."
    ),
    "fct_limit_yearly": (
        "Sous 24 mois d'historique, une somme qui revient une fois par an (un 13e mois, une "
        "prime, un impôt ou une assurance annuels) n'est prévue que si c'est une dépense fixe ; "
        "sinon elle est étalée sur les mois."
    ),
    "fct_limit_euros": "Montants en euros courants, non corrigés de l'inflation.",
    "fct_limit_change": (
        "Un changement dans les mois passés (une augmentation, une aide qui s'arrête) se "
        "retrouve dans les erreurs : la fourchette peut alors pencher d'un côté, comme les "
        "surprises passées."
    ),
    "fct_engine": (
        "{cuts} coupes de back-test sur {n} mois d'historique, graine {seed}, version du moteur "
        "{version}."
    ),
    "fct_m_chronos_2": (
        "Chronos-2, un modèle pré-entraîné sur de nombreuses séries publiques, d'après les seuls "
        "mois de cette catégorie"
    ),
    "fct_m_timesfm": (
        "TimesFM 2.5, un modèle pré-entraîné sur de nombreuses séries publiques, d'après les "
        "seuls mois de cette catégorie"
    ),
    "fct_name_chronos_2": "Chronos-2",
    "fct_name_timesfm": "TimesFM 2.5",
    "fct_bias_expense_less": "{share} de dépenses en moins que ce qui a été saisi",
    "fct_bias_expense_more": "{share} de dépenses en plus que ce qui a été saisi",
    "fct_bias_income_less": "{share} de revenus en moins que ce qui a été reçu",
    "fct_bias_income_more": "{share} de revenus en plus que ce qui a été reçu",
    "fct_bias_savings_less": "{share} d'épargne en moins que ce qui a été épargné",
    "fct_bias_savings_more": "{share} d'épargne en plus que ce qui a été épargné",
    "fct_bias_none": "à peu près ce qui a été saisi",
    "fct_bias_rest_above": "le reste {amount} par mois au-dessus de ce qui restait",
    "fct_bias_rest_below": "le reste {amount} par mois en dessous de ce qui restait",
    "fct_set_aside": (
        "{model} se trompait de {share} en moins mais prévoyait {bias} sur les mois passés "
        "testés : il n'a pas été retenu."
    ),
    "fct_rest_warning": (
        "Sur les mois passés testés, cette prévision plaçait le reste {amount} par mois "
        "au-dessus de ce qui restait : il pourrait être plus bas qu'affiché."
    ),
    "col_bias": "Biais, mois passés testés",
    "fct_limit_prices": (
        "Une hausse des prix plus rapide que sur les mois passés est prévue avec retard : dans "
        "une telle période, la prévision des dépenses peut être basse."
    ),
    "fct_models": "Modèles de fondation : {models}.",
    "fct_no_models": "Modèles de fondation non installés (voir Faire tourner Kwak Finance).",
    "fct_jump_month": "Ce mois",
    "fct_jump_months": "12 mois",
    "fct_jump_targets": "Objectifs",
    "fct_jump_year": "L'année",
    "fct_jump_reliable": "Fiabilité",
    "fct_tile_rest": "Le reste, {first} à {last}",
    "fct_tile_month": "{month} jusqu'ici",
    "fct_tile_targets": "Objectifs du mois",
    "fct_tile_year": "Objectifs {year}",
    "fct_tile_income": "Revenus, 12 mois",
    "fct_tile_spent": "Dépenses, 12 mois",
    "fct_tile_saved": "Épargne, 12 mois",
    "fct_per_month": "environ {amount} par mois",
    "fct_count_over": "dépassement probable : {n}",
    "fct_count_watch": "dépassement possible : {n}",
    "fct_all_within": "tous tenus",
    "fct_at_risk": "{n} à risque sur {of}",
    "fct_months_lede": (
        "Ce qui entre, ce qui sort et ce qui reste chaque mois ; en pointillés, les mois à "
        "venir, leurs bandes tenant environ 8 fois sur 10."
    ),
    "fct_rest_of_month": "Reste du mois",
    "fct_targets_lede": (
        "Chaque catégorie en pourcentage de son objectif : le point est la prévision, la barre "
        "sa fourchette, le trait l'objectif."
    ),
    "fct_year_lede": (
        "En plein, l'année jusqu'ici ; en clair, la prévision jusqu'à décembre ; le trait fin, "
        "la fourchette du total de l'année ; en pourcentage de l'objectif annuel."
    ),
    "fct_to_origin": "Jusqu'à {month}",
    "fct_income_lede": "{month} : la prévision de chaque catégorie de revenus et sa fourchette.",
    "fct_objective_chip": "{name} : {point} pour {target}, {word}",
    "fct_reliable_title": "Fiabilité de la prévision",
    "fct_reliable_hint": (
        "les méthodes, le back-test et les limites : pour vérifier, pas à lire tous les jours"
    ),
    "fct_gain_axis": "Erreur en moins face à la moyenne de 6 mois",
    "fct_bias_axis": "Optimiste à droite",
    "ret_jump_life": "Le parcours",
    "ret_jump_income": "Revenus",
    "ret_jump_fan": "Patrimoine",
    "ret_jump_inputs": "Données",
    "ret_tile_living": "Niveau de vie dès {month}, 9 fois sur 10",
    "ret_per_month": "{amount} par mois",
    "ret_split_pensions": "Pensions {amount}",
    "ret_split_withdrawal": "Retrait {amount}",
    "ret_against": "Dépenses {amount}",
    "ret_tile_covered": "Dépenses couvertes",
    "ret_covered": "couvertes",
    "ret_short": "insuffisant",
    "ret_tile_lasts": "Le patrimoine tient jusqu'à l'horizon",
    "ret_life_title": "Le parcours",
    "ret_life_lede": "Qui travaille, qui touche sa pension, et jusqu'où le plan est testé.",
    "ret_working": "Travaille, {amount}",
    "ret_pension_segment": "Pension {amount}",
    "ret_today": "Aujourd'hui",
    "ret_retires_at": "{name} part à {age} ans",
    "ret_horizon_at": "Horizon : {name} à {age} ans",
    "ret_income_lede": (
        "Les pensions plus le retrait soutenable (9 fois sur 10), face aux dépenses de retraite."
    ),
    "ret_fan_lede": (
        "Le patrimoine net, sa médiane et son éventail, et la part liquide qui paie le retrait."
    ),
    "ret_limits_hint": "impôts, dépendance, décès : ce que le modèle laisse de côté",
    "jump_fan": "Trajectoire",
    "jump_reach": "Un montant",
    "jump_mix": "Par catégorie",
    "jump_whatifs": "Et si",
    "jump_assumptions": "Hypothèses",
    "fan_title": "Le patrimoine net jusqu'à l'horizon",
    "fan_lede": (
        "La médiane et l'éventail des issues ; sur la ligne du montant, quand la moitié puis "
        "neuf dixièmes l'ont atteint."
    ),
    "reach_marks": "Atteint par la moitié, neuf dixièmes",
    "today_bars": "Aujourd'hui",
    "return_axis": "Rendement attendu par an, ± sa volatilité",
    "limits_hint": "ce que le modèle laisse de côté",
    "tile_today": "Patrimoine net aujourd'hui",
    "tile_savings": "{amount} épargnés par mois",
    "tile_median": "Médiane en {month}",
    "tile_range": "entre {low} et {high} 8 fois sur 10",
    "tile_amount": "{amount} en {month}",
    "tile_half": "la moitié des issues l'atteint dès {month}",
}

MESSAGES: Mapping[Language, Mapping[str, str]] = {"en": EN, "fr": FR}

MONTHS: Mapping[Language, tuple[str, ...]] = {
    "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
    "fr": (
        "janv.",
        "févr.",
        "mars",
        "avr.",
        "mai",
        "juin",
        "juil.",
        "août",
        "sept.",
        "oct.",
        "nov.",
        "déc.",
    ),
}

HUNDRED = Decimal(100)


def language(value: str | None) -> Language:
    return "fr" if value == "fr" else "en"


def t(lang: Language, key: str, **values: object) -> str:
    return MESSAGES[lang][key].format(**values)


def number(value: int, lang: Language) -> str:
    """Grouped by thousands: 12,300 or 12 300 (a narrow no-break space, as the app's)."""
    grouped = f"{value:,}"
    return grouped.replace(",", "\u202f") if lang == "fr" else grouped


def money(amount: Decimal, lang: Language) -> str:
    """To the nearest €100, as the projection's amounts (F-SIM-5)."""
    rounded = int((amount / HUNDRED).quantize(Decimal(1), rounding=ROUND_HALF_UP) * HUNDRED)
    sign = "-" if rounded < 0 else ""
    digits = number(abs(rounded), lang)
    return f"{sign}{digits}\u00a0€" if lang == "fr" else f"{sign}€{digits}"


def percent(share: Decimal, lang: Language, *, places: int = 1) -> str:
    """A share as a percentage, to `places` decimals at most: 6.5% or 6,5 %."""
    value = (share * HUNDRED).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    text = f"{value.normalize():f}" if value else "0"
    if lang == "fr":
        return text.replace(".", ",").replace("-", "−") + "\u202f%"
    return text.replace("-", "−") + "%"


def euros(amount: Decimal, lang: Language) -> str:
    """To the nearest euro, as the forecast's amounts (F-FCT-6)."""
    rounded = int(amount.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    sign = "-" if rounded < 0 else ""
    digits = number(abs(rounded), lang)
    return f"{sign}{digits}\u00a0€" if lang == "fr" else f"{sign}€{digits}"


def chance_5(share: Decimal, lang: Language) -> str:
    """To the nearest 5 %, "rare" below 5 % and "nearly always" above 95 % (F-FCT-5)."""
    if share < Decimal("0.05"):
        return t(lang, "fct_rare")
    if share > Decimal("0.95"):
        return t(lang, "fct_nearly")
    rounded = (share * 20).quantize(Decimal(1), rounding=ROUND_HALF_UP) / 20
    return percent(rounded, lang, places=0)


def chance(share: Decimal, lang: Language) -> str:
    """To the whole percent, never 0 nor 100 (F-SIM-5)."""
    if share < Decimal("0.01"):
        return t(lang, "chance_low")
    if share > Decimal("0.99"):
        return t(lang, "chance_high")
    return percent(share, lang, places=0)


def month(m: Month, lang: Language) -> str:
    return f"{MONTHS[lang][m.month - 1]} {m.year}"
