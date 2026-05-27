from app.services.pk_list import load_pk_list


def test_load_pk_list_has_295_items():
    items = load_pk_list()

    assert len(items) == 295
    assert set(items[0]) == {"tg", "tk", "pk"}