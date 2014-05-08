#!/usr/bin/python

def BytesToHuman(num):
    for x in ['bytes','KB','MB','GB']:
        if num < 1024.0 and num > -1024.0:
            return "%3.1f%s" % (num, x)
        num /= 1024.0
    return "%3.1f%s" % (num, 'TB')
    
def SecsToHuman(num):
    if num < 60: return "%d secs" % int(round(num))
    num /= 60.0
    if num < 60: return "%.1f mins" % num
    num /= 60.0
    if num < 24: return "%.1f hours" % num
    return "%.1f days" % num

if __name__ == "__main__":
    print SecsToHuman(23)
    print SecsToHuman(60)
    print SecsToHuman(3800)
    print SecsToHuman(380000)

