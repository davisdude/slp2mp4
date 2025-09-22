from slp2mp4.scoreboard import scoreboard

HEADER_HTML_STR = r"""
<!DOCTYPE html>
<html lang="en">
    <body>
        <div id="container">
            <div class="tournament">
                <div class="tournament-name">{TOURNAMENT_NAME}</div>
                <div class="rule"><hr></div>
                <div class="tournament-location">{TOURNAMENT_LOCATION}</div>
                <div class="rule"><hr></div>
            </div>
            <div class="filler"></div>
"""

FOOTER_HTML_STR = r"""
            <div class="bracket">
                <div class="rule"><hr></div>
                <div class="bracket-info">
                    <span class="bracket-data">{EVENT_NAME}</span>
                    <span class="bracket-data">{PHASE_NAME}</span>
                    <span class="bracket-data">{BRACKET_ROUND_SHORT}</span>
                    <span class="bracket-data">{BRACKET_SCORING_SHORT}</span>
                </div>
            </div>
        </div>
    </body>
</html>
"""

SINGLES_HTML_STR = r"""
            <div class="combatants">
                <div class="rule"><hr></div>
                <div class="combatant">
                    <div class="combatant-team">
                        <div class="combatant-info">
                            <span class="combatant-sponsor">{COMBATANT_1_1_SPONSOR}</span>
                            <span class="combatant-tag">{COMBATANT_1_1_TAG}</span>
                            <span class="combatant-pronouns">{COMBATANT_1_1_PRONOUNS}</span>
                        </div>
                    </div>
                    <span class="combatant-score">{COMBATANT_1_SCORE}</span>
                </div>

                <div class="combatant">
                    <div class="combatant-team">
                        <div class="combatant-info">
                            <span class="combatant-sponsor">{COMBATANT_2_1_SPONSOR}</span>
                            <span class="combatant-tag">{COMBATANT_2_1_TAG}</span>
                            <span class="combatant-pronouns">{COMBATANT_2_1_PRONOUNS}</span>
                        </div>
                    </div>
                    <span class="combatant-score">{COMBATANT_2_SCORE}</span>
                </div>
            </div>
"""

DOUBLES_HTML_STR = r"""
            <div class="combatants">
                <div class="rule"><hr></div>
                <div class="combatant">
                    <div class="combatant-team">
                        <div class="combatant-info">
                            <span class="combatant-sponsor">{COMBATANT_1_1_SPONSOR}</span>
                            <span class="combatant-tag">{COMBATANT_1_1_TAG}</span>
                            <span class="combatant-pronouns">{COMBATANT_1_1_PRONOUNS}</span>
                        </div>
                        <div class="combatant-info">
                            <span class="combatant-sponsor">{COMBATANT_1_2_SPONSOR}</span>
                            <span class="combatant-tag">{COMBATANT_1_2_TAG}</span>
                            <span class="combatant-pronouns">{COMBATANT_1_2_PRONOUNS}</span>
                        </div>
                    </div>
                    <span class="combatant-score">{COMBATANT_1_SCORE}</span>
                </div>

                <div class="combatant">
                    <div class="combatant-team">
                        <div class="combatant-info">
                            <span class="combatant-sponsor">{COMBATANT_2_1_SPONSOR}</span>
                            <span class="combatant-tag">{COMBATANT_2_1_TAG}</span>
                            <span class="combatant-pronouns">{COMBATANT_2_1_PRONOUNS}</span>
                        </div>
                        <div class="combatant-info">
                            <span class="combatant-sponsor">{COMBATANT_2_2_SPONSOR}</span>
                            <span class="combatant-tag">{COMBATANT_2_2_TAG}</span>
                            <span class="combatant-pronouns">{COMBATANT_2_2_PRONOUNS}</span>
                        </div>
                    </div>
                    <span class="combatant-score">{COMBATANT_2_SCORE}</span>
                </div>
            </div>
"""

CSS_STR = r"""
* {
    box-sizing: border-box;
}

html, body {
    color: white;
    background-color: black;
    font-family: "Inconsolata", "Consolas", "monospace";
    height: 100%;
    width: 100%;
    margin: 0 0 0 0;
    padding: 0.5vh 0.5vh 0.5vh 0.5vh;
}

#container {
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

.tournament {
    display: flex;
    flex-direction: column;
    flex-wrap: wrap;
    align-items: center;
}

.rule {
    align-self: stretch;
    flex-grow: 1;
}

.tournament-name, .tournament-location {
    display: flex;
    text-align: center;
}

.tournament-name {
    font-size: 6vh;
}

.tournament-location {
    font-size: 3vh;
}

.filler {
    flex-grow: 1;
}

.combatants {
    display: flex;
    flex-direction: column;
}

.combatant {
    font-size: 4vh;
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    align-items: baseline;
}

.combatant-team {
    flex-direction: column;
}

.combatant-info {
    flex-direction: row;
}

.combatant-sponsor, .combatant-tag, .combatant-pronouns {
    text-align: center;
}

.combatant-sponsor, .combatant-pronouns {
    font-size: 60%;
    color: LightGray;
}

.combatant-score {
    padding-left: 1vh;
    text-align: right;
    flex: 1;
    align-self: center;
}

.bracket {
    font-size: 3vh;
    display: flex;
    flex-direction: column;
}

.bracket-info {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: baseline;
}

.bracket-data {
    text-align: center;
}
"""


class DefaultScoreboard(scoreboard.Scoreboard):
    def _get_scoreboard_panels(self, num_teams: int):
        html_body = SINGLES_HTML_STR if (num_teams == 1) else DOUBLES_HTML_STR
        html_str = HEADER_HTML_STR + html_body + FOOTER_HTML_STR
        return [
            scoreboard.ScoreboardPanel(html_str, CSS_STR, 606 / 1080),
        ]

    def _get_scoreboard_args(self):
        return ("[1]fps=fps=60[1_fps];[1_fps][scaled]hstack=inputs=2[v]",)
