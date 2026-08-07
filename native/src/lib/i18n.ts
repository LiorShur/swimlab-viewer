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

export const dirFor = (lang: Lang) => (lang === "he" ? "rtl" : "ltr");
