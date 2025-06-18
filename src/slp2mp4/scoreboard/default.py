from slp2mp4.scoreboard import scoreboard

HTML_STR = r"""
<!DOCTYPE html>
<html lang="en">
    <body>
        <div class="tournament-name">{TOURNAMENT_NAME}</div>
        <div class="filler"><hr></div>

        <div id="bottom">
            <div class="filler"><hr></div>

            <div class="combatant">
                <span class="combatant-name">{COMBATANT_1_NAME}:</span>
                <span class="combatant-score">{COMBATANT_1_SCORE}</span>
            </div>

            <div class="combatant">
                <span class="combatant-name">{COMBATANT_2_NAME}:</span>
                <span class="combatant-score">{COMBATANT_2_SCORE}</span>
            </div>

            <div class="filler"><hr></div>

            <div class="bracket-info">
                <span class="bracket-info-round">{BRACKET_ROUND}</span>
                <span class="bracket-info-scoring">{BRACKET_SCORING}</span>
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

.combatant {
    font-size: 2.5em;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
}

.combatant-name {
    flex: 1;
    overflow-wrap: break-word;
}

.combatant-score {
    white-space: nowrap;
    text-align: right;
    margin-top: auto;
}

.bracket-info {
    font-size: 2.5em;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    flex-wrap: wrap;
}

.bracket-info-round {
    flex: 1;
    overflow-wrap: break-word;
}

.bracket-info-scoring {
    white-space: nowrap;
    text-align: right;
}
"""


class DefaultScoreboard(scoreboard.Scoreboard):
    def _get_scoreboard_panels(self, pad):
        return [
            scoreboard.ScoreboardPanel(HTML_STR, CSS_STR, 606 / 1080, pad),
        ]

    def _get_scoreboard_args(self):
        return ("[2_cropped][scaled]hstack=inputs=2[v]",)
