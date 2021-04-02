function view_game(player, game, timestamp) {
    window.location.href = "/viewer?player=" + player + "&game=" + game.toString();
}