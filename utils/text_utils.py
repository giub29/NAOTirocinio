# -*- coding: utf-8 -*-

def normalizza_testo_ascii(testo):
    if testo is None:
        return u""

    if not isinstance(testo, unicode):
        try:
            testo = testo.decode("utf-8", "ignore")
        except:
            testo = unicode(testo, errors="ignore")

    sostituzioni = {
        u"à": u"a'", u"è": u"e'", u"é": u"e'",
        u"ì": u"i'", u"ò": u"o'", u"ù": u"u'",
        u"À": u"A'", u"È": u"E'", u"É": u"E'",
        u"Ì": u"I'", u"Ò": u"O'", u"Ù": u"U'"
    }

    for k, v in sostituzioni.items():
        testo = testo.replace(k, v)

    return testo


def testo_per_log(testo):
    return normalizza_testo_ascii(testo)


def testo_per_voce(testo):
    return normalizza_testo_ascii(testo)