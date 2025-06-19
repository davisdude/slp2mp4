from slp2mp4.scoreboard import scoreboard

HTML_STR = r"""
<!DOCTYPE html>
<html lang="en">
    <body>
        <div class="tournament-name">{TOURNAMENT_NAME}</div>
        <div class="filler"><hr></div>
        <div class="tournament-location">{TOURNAMENT_LOCATION}</div>
        <div class="filler"><hr></div>

        <div id="bottom">
            <div class="filler"><hr></div>

            <div class="combatant">
                <span class="combatant-tag">{COMBATANT_1_TAG}:</span>
                <span class="combatant-score">{COMBATANT_1_SCORE}</span>
            </div>

            <div class="combatant">
                <span class="combatant-tag">{COMBATANT_2_TAG}:</span>
                <span class="combatant-score">{COMBATANT_2_SCORE}</span>
            </div>

            <div class="filler"><hr></div>

            <div class="bracket">
                <span class="bracket-data">{EVENT_NAME}</span>
                <span class="bracket-data">{PHASE_NAME}</span>
                <span class="bracket-data">{BRACKET_ROUND_SHORT}</span>
                <span class="bracket-data">{BRACKET_SCORING_SHORT}</span>
            </div>
        </div>
    </body>
</html>
"""

CSS_STR = r"""
body {
    width: 100%;
    height: 100%;
    margin: 0;
    color: white;
    background-color: black;
    font-family: "Inconsolata", "Consolas", "monospace";
}

div {
    margin-left: 0.5em;
    margin-right: 0.5em;
}

#bottom {
    position: absolute;
    bottom: 0px;
    width: inherit;
    margin-left: inherit;
    margin-right: inherit;
}

.tournament-name {
    text-align: center;
    font-size: 5em;
}

.tournament-location {
    text-align: center;
    font-size: 2em;
}

.combatant {
    font-size: 2.5em;
    display: flex;
    align-items: end;
}

.combatant-tag {
    flex: 1;
}

.bracket {
    font-size: 2em;
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
}

.bracket-data {
    text-align: center;
    margin-top: auto;
    margin-bottom: auto;
}
"""


class DefaultScoreboard(scoreboard.Scoreboard):
    def _get_scoreboard_panels(self, pad):
        return [
            scoreboard.ScoreboardPanel(HTML_STR, CSS_STR, 606 / 1080, pad),
        ]

    def _get_scoreboard_args(self):
        return ("[2_cropped][scaled]hstack=inputs=2[v]",)
