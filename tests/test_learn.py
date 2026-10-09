import os

from katrain.core import learn


def test_every_lesson_and_problem_set_is_bundled():
    for i, (_title, name) in enumerate(learn.LESSONS):
        assert os.path.isfile(learn.lesson_path(i)), name
    counts = {set_id: len(learn.problem_files(set_id)) for set_id, _ in learn.PROBLEM_SETS}
    assert counts == {"easy": 140, "intermediate": 140, "hard": 140, "xuanxuan": 347}


def test_problems_are_in_number_order():
    names = [os.path.basename(p) for p in learn.problem_files("easy")[:11]]
    numbers = [int("".join(c for c in n if c.isdigit())) for n in names]
    assert numbers == sorted(numbers)


def test_problem_without_solution_keeps_the_side_to_move():
    for set_id, _ in learn.PROBLEM_SETS:
        for path in learn.problem_files(set_id)[:30]:
            full = learn.problem_tree(path, with_solution=True)
            bare = learn.problem_tree(path)
            assert bare.children == [], path
            assert bare.initial_player == full.initial_player, path
            assert bare.get_list_property("AB") == full.get_list_property("AB"), path


def test_a_white_to_play_problem_starts_with_white():
    found = 0
    for set_id, _ in learn.PROBLEM_SETS:
        for path in learn.problem_files(set_id):
            full = learn.problem_tree(path, with_solution=True)
            if full.initial_player == "W" and "PL" not in full.properties:
                assert learn.problem_tree(path).initial_player == "W", path
                found += 1
                if found >= 5:
                    return
    assert found > 0, "no White-to-play problem without PL found to test"


def test_every_bundled_sgf_parses():
    paths = [learn.lesson_path(i) for i in range(len(learn.LESSONS))]
    for set_id, _ in learn.PROBLEM_SETS:
        paths += learn.problem_files(set_id)
    for p in paths:
        learn.problem_tree(p, with_solution=True)
