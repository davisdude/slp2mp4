from slp2mp4.scoreboard import scoreboard


class DefaultScoreboard(scoreboard.Scoreboard):
    def make_drawtexts(self):
        # TODO: Handle challonge / manual data
        tournament_data = [
            self.context_data["startgg"]["tournament"]["name"],
            self.context_data["startgg"]["tournament"]["location"],
            self.context_data["startgg"]["event"]["name"],
            f"{self.context_data['startgg']['set']['fullRoundText']} (BO{self.context_data['bestOf']})",
        ]
        name_data = [
            scoreboard.get_name_from_slot_data(slot_data)
            for slot_data in self.context_data["scores"][self.game_index]["slots"]
        ]
        lines = [*name_data, "", *tournament_data]
        return [scoreboard.DrawtextContainer(lines)]
