"""Test della lettura del tabellone dei ritardi, con un file sintetico nello stesso formato."""
import pytest

from ritardi import parse_tabellone

RUOTE = ["BARI", "CAGLIARI", "ROMA"]


def _tabellone_ok() -> str:
    righe = ["Rit.\t" + "\t".join(RUOTE)]
    for r in range(18):                       # 18 ritardi x 5 numeri = 90 numeri per ruota
        celle = []
        for i in range(len(RUOTE)):
            nums = [(r * 5 + c + 7 * i) % 90 + 1 for c in range(5)]
            celle += [str(x) for x in nums]
        righe.append(f"{17 - r}\t" + "\t".join(celle))
        if r == 9:
            righe.append("Rit.\t" + "\t".join(RUOTE))      # intestazione ripetuta
    return "\n".join(righe)


def test_parse_ok_and_ranking():
    rit = parse_tabellone(_tabellone_ok())
    assert rit.ruote == RUOTE
    assert all(len(d) == 90 for d in rit.per_ruota.values())
    top = rit.top("BARI", 3)
    assert [r for _, r in top] == [17, 17, 17] and top[0][0] < top[1][0] < top[2][0]
    assert rit.top_assoluti(1)[0][2] == 17


def test_missing_numbers_error():
    testo = _tabellone_ok().replace("\t1\t", "\t\t", 1)
    with pytest.raises(ValueError, match="mancanti"):
        parse_tabellone(testo)


def test_no_header_error():
    with pytest.raises(ValueError, match="intestazione"):
        parse_tabellone("1\t2\t3")
