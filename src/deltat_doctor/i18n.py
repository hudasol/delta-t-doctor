"""English and Arabic text for notes, cause labels and checks.

Notes are created with ``note(key, **params)``. The result is an ordinary English ``str`` that also remembers its key and
parameters, so the same note can be rendered in Arabic with ``note_ar``. The Arabic text was drafted by the author's
assistant and needs a review by a native-speaking engineer before it is shown to customers (see docs/I18N.md).
"""
from __future__ import annotations

EN = {
    "date_ambiguous": "Dates are ambiguous (day/month order); read as day first. Check the first and last date in the report.",
    "duplicates": "{n} duplicate timestamps were averaged (daylight-saving or export overlap).",
    "dropped": "{p} of rows had a missing flow or temperature and were left out.",
    "outlier": "{p} of rows had an impossible flow, temperature or delta-T (spikes, sensor codes) and were left out.",
    "bad_ts": "{p} of timestamps could not be read; those rows were left out.",
    "coerced": "{c} non-numeric cells and {s} sensor-code values (such as -999) were treated as missing.",
    "flatline": "The flow reading repeats exactly for {n} consecutive readings: a stuck or frozen meter. Check the export.",
    "neg_dt": "{p} of running hours show the return colder than the supply (treated as zero delta-T).",
    "no_oat": "No outdoor temperature supplied; diagnosis is less certain (add t_outdoor_c).",
    "order_uncertain": "The order of the top two fixes is uncertain: the ranges for '{a}' and '{b}' overlap. Check both.",
    "ambiguity": ("From meter data alone, constant-flow coils and leaking/passing valves can look alike "
                  "(both keep water moving when load is low). Treat these two as a pair to inspect together."),
    "under25": "Under 25 days of data; use 30+ days (ideally a full year) for a firmer diagnosis.",
    "above_min": ("Delta-T is at or above the contract minimum over this period; no surcharge exposure "
                  "expected, but listed causes may still cost energy."),
    "ood": ("This building's behaviour is unlike anything the model was trained on ({n} of {total} shape measurements "
            "are outside the training range; a normal building shows {limit} or fewer). The ranking below is NOT reliable. "
            "Typical reasons: variable flow that does not follow load, a plant-side loop rather than a building ETS, or a "
            "different system type."),
    "openset": ("This building's combination of behaviours is unlike any building the model was trained on (distance score {s} "
                "against {t} for a normal training building). The cause ranking is withheld because it would not be reliable."),
    "physics_unsupported": "{c}: the model rates this cause likely, but the measured shape does not show the expected signs. Treat it as unconfirmed.",
    "trend": "High-load delta-T is {direction} by about {slope} C per month over {n} windows (Kendall p={p}). Seasonal swings can mimic a trend; check against load and weather.",
    "low_dt": ("Average delta-T ({dt} C) is below the range the model was trained on. If this building was designed for a "
               "low delta-T, the ranking will be overconfident: a design shortfall looks like fouling. Enter the design "
               "delta-T to get an informed diagnosis."),
    "no_design": ("No design delta-T supplied. If you know it, enter it: the diagnosis separates a design "
                  "shortfall from a fault, and it was slightly more accurate in simulation."),
    "coverage": "Only {p} of the hours between the first and last reading have data. Gaps weaken the diagnosis; check the export for missing periods.",
    "seasonal": ("The yearly figures are scaled up from {d} days of data. Cooling demand is seasonal, so a summer-only "
                 "file overstates and a winter-only file understates the year."),
    "flat_flow": "Flow never changes in this file. Check that the flow column is the real meter reading.",
    "design_differs": "Design delta-T differs within the file for {bid} (from {lo} to {hi}); the median was used.",
    "null_ids": "{n} rows had no building id and were grouped as '(no building id)'.",
    "skipped": "{n} building(s) were skipped; see the reason on each row.",
    "blind_count": "{n} building(s) were diagnosed without a design delta-T. Add a design_delta_t_c column for a more reliable result.",
    "savings_overlap": ("Savings are model estimates, summed over causes that may overlap. Treat the total as an upper "
                        "bound on what fixing everything would recover."),
}

AR = {
    "date_ambiguous": "ترتيب اليوم والشهر في التواريخ غير واضح؛ قُرئت التواريخ بصيغة (اليوم/الشهر). راجع أول وآخر تاريخ في التقرير.",
    "duplicates": "تم أخذ متوسط {n} من الطوابع الزمنية المكررة (تغيير توقيت أو تداخل في ملف التصدير).",
    "dropped": "{p} من الصفوف تفتقد قراءة التدفق أو درجة الحرارة، وتم استبعادها.",
    "outlier": "{p} من الصفوف تحوي قيماً مستحيلة للتدفق أو درجة الحرارة أو فرق الحرارة (قفزات أو رموز أعطال الحساسات)، وتم استبعادها.",
    "bad_ts": "تعذّرت قراءة {p} من الطوابع الزمنية، وتم استبعاد تلك الصفوف.",
    "coerced": "عُدّت {c} خلية غير رقمية و{s} قيمة رمزية للحساسات (مثل -999) قيماً مفقودة.",
    "flatline": "قراءة التدفق تتكرر بالقيمة نفسها {n} مرة متتالية، أي أن العدّاد متجمّد أو معطّل. راجع ملف التصدير.",
    "neg_dt": "في {p} من ساعات التشغيل كانت حرارة العودة أبرد من حرارة التغذية (عوملت على أنها فرق حرارة صفر).",
    "no_oat": "لم تُقدَّم درجة الحرارة الخارجية، لذا فالتشخيص أقل يقيناً (أضف العمود t_outdoor_c).",
    "order_uncertain": "ترتيب أول إصلاحين غير مؤكد: النطاقان المتوقعان لـ «{a_ar}» و«{b_ar}» يتداخلان. افحص الاثنين.",
    "ambiguity": ("من بيانات العدّاد وحدها قد يتشابه سلوك الملفات ثابتة التدفق مع الصمامات المتسرّبة، إذ يبقى الماء جارياً "
                  "في الحالتين عند الأحمال المنخفضة. افحصهما معاً."),
    "under25": "البيانات أقل من 25 يوماً؛ استخدم 30 يوماً أو أكثر (ويفضّل سنة كاملة) للحصول على تشخيص أدق.",
    "above_min": "فرق الحرارة عند الحد الأدنى للعقد أو أعلى منه في هذه الفترة، فلا يُتوقع تعرّض لغرامة، لكن الأسباب المدرجة قد تُكلّف طاقة.",
    "ood": ("سلوك هذا المبنى يختلف عمّا تدرّب عليه النموذج ({n} من أصل {total} مؤشراً خارج نطاق التدريب، بينما يُظهر المبنى "
            "المعتاد {limit} أو أقل). الترتيب أدناه غير موثوق. من الأسباب المعتادة: تدفق متغير لا يتبع الحمل، أو دورة على جانب "
            "المحطة بدلاً من محطة نقل الطاقة في المبنى، أو نوع نظام مختلف."),
    "openset": ("مجموعة سلوكيات هذا المبنى لا تشبه أي مبنى تدرّب عليه النموذج (درجة البعد {s} مقابل {t} لمبنى تدريب اعتيادي). "
                "حُجب ترتيب الأسباب لأنه لن يكون موثوقاً."),
    "physics_unsupported": "{c_ar}: يرى النموذج أن هذا السبب مرجّح، لكن الشكل المقيس لا يُظهر العلامات المتوقعة. اعتبره غير مؤكد.",
    "trend": "فرق الحرارة عند الأحمال العالية {direction_ar} بنحو {slope} °م في الشهر عبر {n} نوافذ (قيمة كندال p={p}). التقلبات الموسمية قد تحاكي اتجاهاً؛ قارنه بالحمل والطقس.",
    "low_dt": ("متوسط فرق الحرارة ({dt} °م) أقل من النطاق الذي تدرّب عليه النموذج. إذا صُمّم المبنى لفرق حرارة منخفض فسيكون "
               "الترتيب مبالغاً في ثقته، إذ يشبه القصور التصميمي اتساخ الملفات. أدخل فرق الحرارة التصميمي للحصول على تشخيص مُستنير."),
    "no_design": "لم يُدخل فرق الحرارة التصميمي. إن كنت تعرفه فأدخله: فهو يميّز القصور التصميمي عن العطل، وكان أدق قليلاً في المحاكاة.",
    "coverage": "{p} فقط من الساعات بين أول قراءة وآخر قراءة فيها بيانات. الفجوات تُضعف التشخيص؛ تحقّق من ملف التصدير بحثاً عن فترات ناقصة.",
    "seasonal": ("الأرقام السنوية مُستقرأة من {d} يوماً من البيانات. الطلب على التبريد موسمي، لذا يبالغ ملف الصيف في تقدير "
                 "السنة ويقلّل ملف الشتاء من تقديرها."),
    "flat_flow": "التدفق لا يتغير إطلاقاً في هذا الملف. تأكد من أن عمود التدفق هو قراءة العدّاد الفعلية.",
    "design_differs": "فرق الحرارة التصميمي يختلف داخل الملف للمبنى {bid} (من {lo} إلى {hi})؛ استُخدم الوسيط.",
    "null_ids": "{n} صفاً بلا معرّف مبنى جُمعت تحت «(no building id)».",
    "skipped": "تم تخطي {n} مبنى؛ راجع السبب في كل صف.",
    "blind_count": "شُخّص {n} مبنى دون فرق حرارة تصميمي. أضف العمود design_delta_t_c لنتيجة أوثق.",
    "savings_overlap": "الوفورات تقديرات من النموذج ومجموعة على أسباب قد تتداخل، فاعتبر الإجمالي حدّاً أعلى لما يستردّه إصلاح كل شيء.",
}

CAUSE_SHORT_EN = {"fouling": "Fouled coils", "passing_valves": "Leaking valves",
                  "constant_flow": "Constant-flow coils", "overflow": "Excess flow at part load"}
CAUSE_SHORT_AR = {"fouling": "اتساخ الملفات", "passing_valves": "صمامات متسرّبة",
                  "constant_flow": "ملفات ثابتة التدفق", "overflow": "تدفق زائد عند الحمل الجزئي"}
CAUSE_LABELS_AR = {
    "fouling": "اتساخ الملفات أو المبادل الحراري",
    "passing_valves": "صمامات متسرّبة (ماء يمرّ عبر ملفات متوقفة)",
    "constant_flow": "ملفات ثابتة التدفق (صمامات ثلاثية الاتجاه أو مشغّلات عالقة في الوضع المفتوح)",
    "overflow": "تدفق زائد عند الحمل الجزئي (فرق ضغط زائد أو صمامات كبيرة الحجم أو متذبذبة)",
}
CHECKS_AR = {
    "fouling": [
        "تتبّع فرق حرارة الملف مقابل الحمل لكل وحدة معالجة هواء (من نظام إدارة المبنى)؛ فالملفات المتّسخة تفقد فرق الحرارة أكثر عند الأحمال العالية.",
        "افحص زعانف الملفات ونظّفها، ونظّف المرشّحات والمصافي والمبادل الحراري الصفائحي في محطة نقل الطاقة.",
        "افحص التلوّث على جانب الماء في دورة المبنى (جرعات المعالجة، جودة الماء، هبوط الضغط عبر المبادل الصفائحي).",
    ],
    "passing_valves": [
        "قارن أمر صمام التحكم لكل وحدة معالجة هواء بفرق حرارة الملف عندما تكون الوحدة متوقفة أو الأمر قريباً من صفر بالمئة.",
        "اختبر الصمامات ثنائية الاتجاه بحثاً عن تسرّب، وافحص المشغّلات والوصلات؛ وابحث عن أنابيب عودة باردة على ملفات متوقفة.",
        "تحقّق من قفل التشغيل المتبادل بحيث تُغلق الصمامات عند توقف المروحة أو المنطقة.",
    ],
    "constant_flow": [
        "حدّد أي صمامات ثلاثية الاتجاه ما زالت في الخدمة واستبدلها بصمامات ثنائية الاتجاه (ويفضّل أن تكون مستقلة عن الضغط).",
        "ابحث عن مشغّلات عالقة في الوضع المفتوح أو في وضع اليدوي/التجاوز، وعن صمامات ثابتة الوضع.",
        "تأكد من أن مضخات المبنى متغيّرة السرعة وتتبع الطلب.",
    ],
    "overflow": [
        "راجع نقطة ضبط فرق الضغط الثانوي ومنحنى المضخة، وخفّض الضغط الزائد.",
        "افحص أحجام الصمامات وقدرتها على التحكم؛ وابحث عن صمامات متذبذبة وفروع غير متوازنة.",
        "فكّر في صمامات تحكم مستقلة عن الضغط مع وظيفة تحديد فرق الحرارة.",
    ],
}
DISCLAIMER_AR = ("تشخيص إحصائي من بيانات عدّاد محطة نقل الطاقة. يرتّب الأسباب المحتملة لتفحصها أولاً، ولا يغني عن المسح الميداني. "
                 "جرى تدريبه واختباره على مبانٍ محاكاة فقط، ولم يُتحقق منه ببيانات ميدانية من دولة الإمارات.")


class Note(str):
    """An English note that remembers its key and parameters so it can be rendered in Arabic."""
    key: str
    params: dict


def note(key: str, **params) -> Note:
    n = Note(EN[key].format(**params))
    n.key, n.params = key, params
    return n


def note_ar(n) -> str:
    key = getattr(n, "key", None)
    if key is None or key not in AR:
        return str(n)
    p = dict(getattr(n, "params", {}))
    try:
        return AR[key].format(**p)
    except KeyError:
        return str(n)
