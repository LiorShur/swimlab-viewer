// Drills library — verified free demo videos + bilingual how-to, ported verbatim
// from the web app (src/app_template.html) so the two stay in sync. Keyed by the
// placement the drill helps.
import type { Lang } from "./i18n";

export type Drill = {
  yt: string; // YouTube video id
  name: Record<Lang, string>;
  howto: Record<Lang, string>;
};

export const DRILLS: Record<string, Drill[]> = {
  head: [
    {
      yt: "kno0orQgy2Q",
      name: { en: "One-goggle-out cue", he: "רמז משקף אחד בחוץ" },
      howto: {
        en: "As you breathe, rotate just enough to clear your mouth while keeping the lower goggle in the water. It caps how far you turn and stops the head from lifting. Try a length breathing every 3, checking one goggle stays under each breath.",
        he: "בזמן הנשימה, סובב רק עד שהפה יוצא מהמים, תוך שמירה על המשקף התחתון בתוך המים. זה מגביל את מידת הסיבוב ומונע הרמת ראש. נסה אורך בריכה בנשימה כל 3, וודא שמשקף אחד נשאר מתחת למים בכל נשימה.",
      },
    },
    {
      yt: "Gq2asyrI0MI",
      name: { en: "Exhale-pattern breathing", he: "נשיפה מבוקרת" },
      howto: {
        en: "Breathe out steadily through nose and mouth the whole time your face is in the water, so you only inhale when you turn to air. A continuous stream of bubbles removes the rushed, late breath and the head-lift that comes with it.",
        he: "נשוף באופן רציף דרך האף והפה כל עוד הפנים במים, כך שתשאף רק כשאתה פונה לאוויר. זרם בועות קבוע מבטל את הנשימה החפוזה והמאוחרת ואת הרמת הראש שנלווית אליה.",
      },
    },
    {
      yt: "uoAhTVn3v5I",
      name: { en: "Steady low-head position", he: "ראש נמוך ויציב" },
      howto: {
        en: "Swim relaxed with your eyes down and slightly forward and the waterline around the crown of your head — a neutral, low head position. Hold it steady, especially late in a set as you tire, so the head doesn't creep up.",
        he: "שחה רגוע כשהמבט למטה ומעט קדימה וקו המים סביב קודקוד הראש — תנוחת ראש ניטרלית ונמוכה. שמור עליה יציבה, במיוחד בסוף סט כשאתה מתעייף, כדי שהראש לא יזחל כלפי מעלה.",
      },
    },
  ],
  sacrum: [
    {
      yt: "1VQVfo0icr0",
      name: { en: "Side-kick balance", he: "איזון בעיטה על הצד" },
      howto: {
        en: "Kick on your side, lower arm extended, top arm resting along your body, head down and cheek on the water. Hold a steady kick and balance, rotating just to breathe. Builds the body roll that lets the breath come from rotation, not a lift.",
        he: "בעט על הצד, היד התחתונה מושטת, העליונה צמודה לגוף, הראש למטה והלחי על המים. שמור על בעיטה יציבה ואיזון, וסובב רק כדי לנשום. בונה את גלגול הגוף שמאפשר לנשימה לבוא מסיבוב ולא מהרמה.",
      },
    },
    {
      yt: "1rKCME8HfJY",
      name: { en: "6-kick / 3-stroke switch", he: "6 בעיטות / 3 תנועות מעבר" },
      howto: {
        en: "Push off on your side, one arm extended, the other at your side, head down. Take 6 kicks in that balanced position, then one stroke and switch to the other side for 6 more. The pause on each side grooves rotation and timing.",
        he: "דחוף מהקיר על הצד, יד אחת מושטת והשנייה צמודה לגוף, הראש למטה. בצע 6 בעיטות בתנוחה מאוזנת זו, ואז תנועת חתירה אחת ומעבר לצד השני ל-6 נוספות. ההשהיה בכל צד מחריצה את הסיבוב והתזמון.",
      },
    },
    {
      yt: "QImNLwVYEmc",
      name: { en: "Bilateral breathing (every 3)", he: "נשימה דו-צדדית (כל 3)" },
      howto: {
        en: "Breathe every 3 strokes so you alternate sides. It evens out a strong/weak side and builds a symmetric stroke. If every-3 feels breathless at first, alternate by length (breathe left one length, right the next) and build up.",
        he: "נשום כל 3 תנועות כך שאתה מתחלף בין הצדדים. זה מאזן בין צד חזק לחלש ובונה חתירה סימטרית. אם כל-3 מקשה בהתחלה, התחלף לפי אורך בריכה (שמאלה אורך אחד, ימינה בהמשך) והגדל בהדרגה.",
      },
    },
  ],
  wrist: [
    {
      yt: "qp5wUg5obpM",
      name: { en: "Single-arm freestyle", he: "חתירה ביד אחת" },
      howto: {
        en: "Swim freestyle using one arm only; the other stays extended in front (or resting at your side). Focus on a clean catch and full pull on the working arm. Do a length on each arm — fins help you keep momentum. Great for evening out a dominant arm.",
        he: "שחה חתירה עם יד אחת בלבד; השנייה מושטת קדימה (או צמודה לגוף). התמקד בתפיסה נקייה ומשיכה מלאה של היד הפעילה. בצע אורך בריכה לכל יד — סנפירים עוזרים לשמור על תנופה. מצוין לאיזון יד דומיננטית.",
      },
    },
    {
      yt: "1rKCME8HfJY",
      name: { en: "6-kick / 3-stroke switch", he: "6 בעיטות / 3 תנועות מעבר" },
      howto: {
        en: "Push off on your side, one arm extended, the other at your side, head down. Take 6 kicks, then one stroke and switch. The pause grooves the entry and the crossover timing between the two arms.",
        he: "דחוף מהקיר על הצד, יד אחת מושטת והשנייה צמודה, הראש למטה. בצע 6 בעיטות, ואז תנועה אחת ומעבר. ההשהיה מחריצה את הכניסה ואת תזמון המעבר בין שתי הידיים.",
      },
    },
    {
      yt: "QImNLwVYEmc",
      name: { en: "Bilateral breathing (every 3)", he: "נשימה דו-צדדית (כל 3)" },
      howto: {
        en: "Breathe every 3 strokes to alternate sides. It balances left/right timing and stroke length between the arms, so one arm stops doing more of the work than the other.",
        he: "נשום כל 3 תנועות כדי להתחלף בין הצדדים. זה מאזן תזמון ואורך תנועה בין הידיים, כך שיד אחת מפסיקה לעשות יותר מהעבודה.",
      },
    },
  ],
};
