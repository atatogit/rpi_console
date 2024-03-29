#!/usr/bin/python

from levenshtein import levenshtein


__REMOVABLE_STRINGS = set(("[ettv]", "[eztv]"))


def __NormalizeForMatchScore(s):
    normalized = s.strip().replace(" ", ".").lower()
    for to_remove in __REMOVABLE_STRINGS:
        normalized = normalized.replace(to_remove, "")
    return normalized.strip()


def ScoreSubtitleMatch(query, sub_name):
    normalized_query = __NormalizeForMatchScore(query)
    normalized_sub_name = __NormalizeForMatchScore(sub_name)
    return levenshtein(normalized_query, normalized_sub_name)
