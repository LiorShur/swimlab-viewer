// Minimal bilingual strings (EN + HE, masculine singular), matching the web
// app's convention. Hebrew is the default and drives RTL.
export type Lang = "he" | "en";

export const STR: Record<Lang, Record<string, string>> = {
  en: {
    appName: "swimlab",
    tagline: "multi-sensor swim analysis",
    signIn: "Sign in",
    signOut: "Sign out",
    google: "Continue with Google",
    or: "or",
    email: "Email",
    password: "Password",
    createAccount: "Create account",
    haveAccount: "Have an account? Sign in",
    needAccount: "Need an account? Create one",
    history: "History",
    noSwims: "No saved swims yet.",
    importRec: "Import recordings",
    processing: "Processing…",
    narrate: "Narrate with AI",
    narrating: "Narrating…",
    upgrade: "AI narration is a paid feature — upgrade to unlock it.",
    play: "Play",
    pause: "Pause",
    speed: "Speed",
    connectSensor: "Connect DOT sensor",
    savedOk: "Saved to your account ✓",
    langToggle: "עברית",
    analysis: "Analysis",
    coaching: "Coaching points",
    aiSummary: "AI summary",
    incompleteTitle: "Analysis incomplete",
    incompleteBody: "This file may have no calibration at the start, so it couldn't be analysed properly. For real results, re-import this sensor with its separate calibration files.",
    incompleteCta: "Add calibration files",
    drillsLib: "Drills to try",
    drillWatch: "▶ Watch",
    drillHowto: "▾ How to",
    drillClose: "Close",
    drillOpenYt: "Open on YouTube ↗",
    navHome: "Home", navCapture: "Capture", navHistory: "History", navSettings: "Settings",
    homeWelcome: "Welcome to swimlab", homeSub: "Import a swim or connect a DOT sensor to see your analysis.",
    homeImportCta: "Import a swim", homeNoSwim: "No swim loaded yet.",
    captureTitle: "Capture a swim", captureSub: "Add one sensor file per DOT — one or several per swim.",
    captureConnectSoon: "DOT sensor connect — coming soon",
    wizPlacement: "Placement", wizFiles: "Files", wizSingle: "Single file", wizCalset: "Trial + calibration",
    wizTrial: "Swim file", wizT0a: "Calibration A (upright)", wizT0b: "Calibration B (face-down)",
    wizPick: "Choose file…", wizAddBtn: "Add to session", wizRemove: "Remove",
    wizAddSensor: "Add a sensor", wizProcess: "Process session", wizEmpty: "Add one or more sensor files, then process the swim.",
    wizAddFiles: "＋ Add sensor files", wizAddFilesHint: "One file per sensor — pick one or several at once.",
    wizAdvanced: "Sensor with separate calibration files (advanced)", wizAdvancedAdd: "Add this sensor",
    wizReplace: "Replace file",
    wizProvisional: "Single-file calibration reads the poses from the start of the file — provisional until validated on a real recording.",
    wizDup: "That placement is already added.",
    wizDetecting: "Checking…", wizInspecting: "Inspecting files…", wizConsistent: "looks consistent with your choice",
    wizMismatchWrist: "This looks like a wrist sensor — double-check the placement.",
    wizMismatchBody: "This looks like a body sensor (head/sacrum) — double-check the placement.",
    settingsTitle: "Settings", settAccount: "Account", settTier: "Plan", settLanguage: "Language",
    settAbout: "About", tierFree: "Free", tierPaid: "Paid",
    aboutText: "swimlab — head/sacrum/wrist swim analysis from Movella DOT sensors.",
    obNext: "Next", obSkip: "Skip", obStart: "Get started",
    ob1t: "See your stroke, measured", ob1b: "swimlab turns Movella DOT sensor recordings into clear, per-placement analysis of your freestyle.",
    ob2t: "Head, sacrum, wrists", ob2b: "Clip a sensor where you want insight — breathing (head), body roll (sacrum), or arm symmetry (wrists) — one or several per swim.",
    ob3t: "Analysis, drills, and AI", ob3b: "Get metrics, a plain-language read, matched drills with videos, and optional AI narration in English or Hebrew.",
  },
  he: {
    appName: "swimlab",
    tagline: "ניתוח שחייה רב-חיישני",
    signIn: "התחברות",
    signOut: "התנתקות",
    google: "המשך עם Google",
    or: "או",
    email: "אימייל",
    password: "סיסמה",
    createAccount: "יצירת חשבון",
    haveAccount: "יש לך חשבון? התחבר",
    needAccount: "אין לך חשבון? צור אחד",
    history: "היסטוריה",
    noSwims: "אין עדיין שחיות שמורות.",
    importRec: "ייבוא הקלטות",
    processing: "מעבד…",
    narrate: "נתח עם AI",
    narrating: "מנתח…",
    upgrade: "ניתוח AI הוא תכונה בתשלום — שדרג כדי לפתוח אותה.",
    play: "נגן",
    pause: "השהה",
    speed: "מהירות",
    connectSensor: "חבר חיישן DOT",
    savedOk: "נשמר לחשבון שלך ✓",
    langToggle: "English",
    analysis: "ניתוח",
    coaching: "נקודות אימון",
    aiSummary: "סיכום AI",
    incompleteTitle: "ניתוח לא שלם",
    incompleteBody: "ייתכן שלקובץ אין כיול בתחילתו, ולכן לא ניתן היה לנתח אותו כראוי. לתוצאות אמיתיות, ייבא מחדש את החיישן עם קובצי הכיול הנפרדים שלו.",
    incompleteCta: "הוסף קובצי כיול",
    drillsLib: "תרגילים לתרגול",
    drillWatch: "▶ צפה",
    drillHowto: "▾ איך",
    drillClose: "סגור",
    drillOpenYt: "פתח ביוטיוב ↗",
    navHome: "בית", navCapture: "הקלטה", navHistory: "היסטוריה", navSettings: "הגדרות",
    homeWelcome: "ברוך הבא ל-swimlab", homeSub: "ייבא שחייה או חבר חיישן DOT כדי לראות את הניתוח שלך.",
    homeImportCta: "ייבוא שחייה", homeNoSwim: "עדיין לא נטענה שחייה.",
    captureTitle: "הקלטת שחייה", captureSub: "הוסף קובץ אחד לכל חיישן DOT — אחד או כמה לשחייה.",
    captureConnectSoon: "חיבור חיישן DOT — בקרוב",
    wizPlacement: "מיקום", wizFiles: "קבצים", wizSingle: "קובץ יחיד", wizCalset: "שחייה + כיול",
    wizTrial: "קובץ שחייה", wizT0a: "כיול A (זקוף)", wizT0b: "כיול B (פנים למטה)",
    wizPick: "בחר קובץ…", wizAddBtn: "הוסף למפגש", wizRemove: "הסר",
    wizAddSensor: "הוסף חיישן", wizProcess: "עבד מפגש", wizEmpty: "הוסף קובץ חיישן אחד או יותר, ואז עבד את השחייה.",
    wizAddFiles: "＋ הוסף קבצי חיישן", wizAddFilesHint: "קובץ אחד לכל חיישן — בחר אחד או כמה בבת אחת.",
    wizAdvanced: "חיישן עם קובצי כיול נפרדים (מתקדם)", wizAdvancedAdd: "הוסף חיישן זה",
    wizReplace: "החלף קובץ",
    wizProvisional: "כיול מקובץ יחיד קורא את התנוחות מתחילת הקובץ — זמני עד לאימות על הקלטה אמיתית.",
    wizDup: "המיקום הזה כבר נוסף.",
    wizDetecting: "בודק…", wizInspecting: "בודק קבצים…", wizConsistent: "נראה תואם לבחירה שלך",
    wizMismatchWrist: "נראה כמו חיישן פרק יד — בדוק שוב את המיקום.",
    wizMismatchBody: "נראה כמו חיישן גוף (ראש/אגן) — בדוק שוב את המיקום.",
    settingsTitle: "הגדרות", settAccount: "חשבון", settTier: "מסלול", settLanguage: "שפה",
    settAbout: "אודות", tierFree: "חינם", tierPaid: "בתשלום",
    aboutText: "swimlab — ניתוח שחייה לראש/אגן/פרק יד מחיישני Movella DOT.",
    obNext: "הבא", obSkip: "דלג", obStart: "בוא נתחיל",
    ob1t: "ראה את החתירה שלך, נמדדת", ob1b: "swimlab הופך הקלטות מחיישני Movella DOT לניתוח ברור של החתירה שלך, לפי מיקום.",
    ob2t: "ראש, אגן, פרקי יד", ob2b: "חבר חיישן היכן שתרצה תובנה — נשימה (ראש), גלגול גוף (אגן) או סימטריית ידיים (פרקי יד) — אחד או כמה לשחייה.",
    ob3t: "ניתוח, תרגילים ו-AI", ob3b: "קבל מדדים, קריאה בשפה פשוטה, תרגילים מתאימים עם סרטונים, וניתוח AI אופציונלי באנגלית או עברית.",
  },
};

// Per-placement one-line description (mirrors the web app's banners).
export const BANNER: Record<Lang, Record<string, string>> = {
  en: {
    head: "Head (skull): breath technique — head-lift (Δpitch) vs rotation (roll), the lifter/rotator gate.",
    sacrum: "Sacrum (pelvis): whole-body roll + push-offs → lengths, distance, stroke count, tempo, L/R roll symmetry.",
    wrist: "Wrist (forearm L+R): per-arm stroke phases from forearm pitch → stroke count/rate, plus the L/R symmetry fusion metric.",
  },
  he: {
    head: "ראש: טכניקת נשימה — הרמת ראש (Δpitch) מול סיבוב (roll), קו ההפרדה מרים/מסתובב.",
    sacrum: "אגן: סיבוב גוף מלא + דחיפות קיר → אורכים, מרחק, מספר תנועות, טמפו, סימטריית סיבוב ימין/שמאל.",
    wrist: "פרק יד (אמה ימין+שמאל): שלבי משיכה לכל יד מזווית האמה → מספר/קצב תנועות, ומדד סימטריית ימין/שמאל.",
  },
};

// Friendly labels + units for known summary metrics; unknowns fall back to the
// humanised key.
export const KPI_LABEL: Record<Lang, Record<string, string>> = {
  en: {
    mean_d_pitch_breath: "Mean Δpitch", peak_roll_breath: "Peak roll",
    roll_pitch_ratio: "Roll:pitch ratio", asymmetry_index: "Asymmetry index",
    pitch_variability: "Variability (SD)", body_roll_amplitude_deg: "Body roll",
    roll_symmetry_index: "Roll symmetry", stroke_count: "Stroke count",
    distance_m: "Distance", lengths: "Lengths", tempo_spm: "Tempo",
    pitch_amplitude_deg: "Pitch amplitude",
  },
  he: {
    mean_d_pitch_breath: "Δpitch ממוצע", peak_roll_breath: "שיא סיבוב",
    roll_pitch_ratio: "יחס רול:פיץ׳", asymmetry_index: "מדד אי-סימטריה",
    pitch_variability: "שונות (סטיית תקן)", body_roll_amplitude_deg: "סיבוב גוף",
    roll_symmetry_index: "סימטריית סיבוב", stroke_count: "מספר תנועות",
    distance_m: "מרחק", lengths: "אורכים", tempo_spm: "טמפו",
    pitch_amplitude_deg: "טווח פיץ׳",
  },
};

export const KPI_UNIT: Record<string, string> = {
  mean_d_pitch_breath: "°", peak_roll_breath: "°", body_roll_amplitude_deg: "°",
  pitch_variability: "°", pitch_amplitude_deg: "°", distance_m: "m", tempo_spm: "spm",
};

// Placement ids the capture wizard offers, with bilingual labels.
export const PLACEMENTS = ["head", "sacrum", "wrist_l", "wrist_r", "ankle_l", "ankle_r", "uparm_l", "uparm_r"] as const;
export const PLACEMENT_LABEL: Record<Lang, Record<string, string>> = {
  en: { head: "Head", sacrum: "Sacrum", wrist: "Wrist", wrist_l: "Wrist L", wrist_r: "Wrist R",
        ankle_l: "Ankle L", ankle_r: "Ankle R", uparm_l: "Upper arm L", uparm_r: "Upper arm R" },
  he: { head: "ראש", sacrum: "אגן", wrist: "פרק יד", wrist_l: "פרק יד ש", wrist_r: "פרק יד י",
        ankle_l: "קרסול ש", ankle_r: "קרסול י", uparm_l: "זרוע ש", uparm_r: "זרוע י" },
};

export const MOTION_TITLE: Record<Lang, string> = { en: "Motion", he: "תנועה" };

// Per-placement caption for the motion schematic (mirrors the web app).
export const MOTION_HINT: Record<Lang, Record<string, string>> = {
  en: {
    head: "A simple schematic driven by the recorded traces: the head rolls (rotation) and pitches (lift) as it did in the swim.",
    sacrum: "A rear view of the torso rolling side to side, driven by the recorded body-roll trace.",
    wrist: "The two forearms swinging through catch → pull → recovery, driven by each arm's pitch — antiphase, as recorded.",
  },
  he: {
    head: "סכמה פשוטה המונעת מהמדידות: הראש מתגלגל (סיבוב) ומתרומם (פיץ׳) כפי שהיה בשחייה.",
    sacrum: "מבט מאחור על הגו המתגלגל מצד לצד, מונע מאות סיבוב-הגוף שנמדד.",
    wrist: "שתי האמות נעות דרך תפיסה → משיכה → התאוששות, מונע מזווית כל יד — באנטי-פאזה, כפי שנמדד.",
  },
};

export const dirFor = (lang: Lang) => (lang === "he" ? "rtl" : "ltr");
