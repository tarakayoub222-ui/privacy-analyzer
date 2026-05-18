from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
import re
import json

load_dotenv()

# محاولة استيراد Gemini إذا كان متاحاً
try:
    import google.generativeai as genai
    GEMINI_API_KEY = os.getenv('AIzaSyDiUR8edBkbNahybp-Exo_gIpyVSKayChU')
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')
        print('✅ Gemini API مهيأ بنجاح')
    else:
        print('⚠️ مفتاح Gemini API غير موجود في ملف .env')
        model = None
except ImportError:
    print('⚠️ مكتبة google.generativeai غير مثبتة')
    model = None

app = Flask(__name__)
CORS(app)  # السماح لكل المواقع بالاتصال

@app.route('/')
def home():
    return jsonify({
        'status': 'ok',
        'message': 'الخادم يعمل',
        'version': '2.0.0'
    })

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'server': 'running',
        'gemini': 'active' if model else 'inactive'
    })

# ============================================
# ⚡ API الرئيسي لتحليل سياسة الخصوصية
# ============================================
@app.route('/analyze', methods=['POST'])
def analyze():
    """
    API لتحليل سياسة الخصوصية
    المدخلات: JSON مع حقل 'text' يحتوي على نص السياسة
    المخرجات: JSON مع نسبة الخطر وقائمة المخاطر والملخص
    """
    try:
        data = request.get_json()
        text = data.get('text', '')
        
        print(f"\n{'='*60}")
        print(f"📥 تم استلام نص بطول {len(text)} حرف")
        print(f"{'='*60}")
        
        if not text:
            return jsonify({'error': 'النص مطلوب'}), 400
        
        # محاولة استخدام Gemini أولاً إذا كان متاحاً
        if model:
            print("🔄 محاولة التحليل باستخدام Gemini...")
            gemini_result = analyze_with_gemini(text)
            if gemini_result:
                print(f"✅ تم التحليل باستخدام Gemini: {gemini_result['risk_score']}%")
                return jsonify(gemini_result)
            else:
                print("⚠️ فشل تحليل Gemini، نستخدم التحليل اليدوي")
        
        # استخدام التحليل اليدوي المتقدم
        print("🔄 استخدام التحليل اليدوي المتقدم...")
        
        # تحليل النص الكامل بتقسيمه إذا كان طويلاً
        if len(text) > 10000:
            print(f"📊 النص طويل ({len(text)} حرف)، نستخدم التحليل المقسم")
            score, risks, details = analyze_full_text(text)
            method = 'full'
        else:
            print(f"📊 النص قصير، نستخدم التحليل المباشر")
            score, risks, details = analyze_text_segment(text)
            method = 'simple'
        
        # توليد الملخص
        if score < 30:
            summary = "✅ سياسة خصوصية منخفضة المخاطر. تبدو الممارسات آمنة نسبياً."
            color = "green"
        elif score < 60:
            summary = "⚠️ سياسة خصوصية متوسطة المخاطر. هناك بعض الممارسات التي تستحق الانتباه."
            color = "orange"
        else:
            summary = "🔴 سياسة خصوصية عالية المخاطر. يُنصح بالحذر الشديد."
            color = "red"
        
        result = {
            'risk_score': round(score),
            'risks': risks[:7],  # حد أقصى 7 مخاطر
            'summary': summary,
            'color': color,
            'text_length': len(text),
            'analysis_method': method,
            'details': details
        }
        
        print(f"📊 نتيجة التحليل: {score}%")
        print(f"📋 عدد المخاطر: {len(risks)}")
        print(f"{'='*60}\n")
        
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ خطأ في التحليل: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================
# دوال التحليل المساعدة
# ============================================

def analyze_with_gemini(text):
    """
    تحليل النص باستخدام Gemini API
    """
    try:
        # تحديد الطول المناسب لـ Gemini
        max_length = 25000
        if len(text) > max_length:
            text = text[:max_length]
            print(f"⚠️ تم اقتطاع النص إلى {max_length} حرف لـ Gemini")
        
        prompt = f"""
        أنت خبير في تحليل سياسات الخصوصية. قم بتحليل النص التالي بدقة عالية.
        
        تعليمات مهمة:
        1. اقرأ النص كاملاً بتركيز
        2. حدد جميع الممارسات التي تشكل خطراً على خصوصية المستخدم
        3. قيم مستوى الخطر بناءً على:
           - أنواع البيانات المجمعة (حساسة/غير حساسة)
           - أغراض المعالجة (تسويق/مشاركة/بيع)
           - مدة الاحتفاظ بالبيانات
           - حقوق المستخدم
           - وجود تدابير أمنية
        4. قدم نسبة خطر دقيقة (0-100)
        5. اذكر جميع المخاطر المحددة
        6. قدم ملخصاً شاملاً
        
        نص سياسة الخصوصية:
        {text}
        
        أعد النتيجة بتنسيق JSON فقط (بدون أي نصوص إضافية):
        {{
            "risk_score": (رقم بين 0-100),
            "risks": ["خطر 1", "خطر 2", "خطر 3"],
            "summary": "ملخص شامل بالعربية يشرح النتيجة"
        }}
        """
        
        response = model.generate_content(prompt)
        
        # استخراج JSON من الرد
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            # إضافة حقول إضافية
            result['text_length'] = len(text)
            result['analysis_method'] = 'gemini'
            return result
        
    except Exception as e:
        print(f"⚠️ خطأ في Gemini: {e}")
    
    return None


def analyze_full_text(text):
    """
    تحليل النص الكامل بتقسيمه إلى أجزاء
    """
    # تقسيم النص إلى أجزاء (كل جزء 5000 كلمة)
    words = text.split()
    chunk_size = 5000
    chunks = []
    
    for i in range(0, len(words), chunk_size):
        chunk = ' '.join(words[i:i+chunk_size])
        chunks.append(chunk)
    
    print(f"📊 تم تقسيم النص إلى {len(chunks)} جزء")
    
    # تحليل كل جزء على حدة
    all_risks = []
    total_score = 0
    all_details = {}
    
    for i, chunk in enumerate(chunks):
        print(f"🔍 تحليل الجزء {i+1}/{len(chunks)}...")
        
        # تحليل هذا الجزء
        chunk_score, chunk_risks, chunk_details = analyze_text_segment(chunk)
        
        total_score += chunk_score
        all_risks.extend(chunk_risks)
        
        # دمج التفاصيل
        for key, value in chunk_details.items():
            if key not in all_details:
                all_details[key] = value
            elif isinstance(value, list):
                if key not in all_details:
                    all_details[key] = []
                all_details[key].extend(value)
    
    # حساب المتوسط للنتيجة النهائية
    avg_score = total_score / len(chunks) if chunks else 50
    
    # إزالة تكرار المخاطر
    unique_risks = []
    for risk in all_risks:
        if risk not in unique_risks:
            unique_risks.append(risk)
    
    return avg_score, unique_risks, all_details


def analyze_text_segment(text_segment):
    """
    تحليل جزء من النص
    """
    text_lower = text_segment.lower()
    score = 30  # درجة افتراضية
    
    # ============================================
    # قائمة الكلمات التي تزيد الخطر (موسعة)
    # ============================================
    high_risk_words = {
        # مشاركة البيانات
        'share': 8,
        'third party': 10,
        'third-parties': 10,
        'sell': 15,
        'rent': 12,
        'trade': 12,
        'disclose': 7,
        
        # أنواع البيانات الحساسة
        'location': 8,
        'gps': 8,
        'biometric': 15,
        'fingerprint': 15,
        'face id': 15,
        'health': 12,
        'medical': 12,
        'financial': 10,
        'credit card': 10,
        'ssn': 15,
        'social security': 15,
        'browsing history': 8,
        'search history': 8,
        'contacts': 8,
        'messages': 8,
        'photos': 6,
        
        # التتبع والمراقبة
        'track': 8,
        'monitor': 8,
        'analyze': 5,
        'profile': 6,
        
        # الاحتفاظ بالبيانات
        'retain': 5,
        'indefinitely': 10,
        'as long as necessary': 3,
        'for legal purposes': 2,
        
        # الإعلانات والتسويق
        'advertising': 8,
        'marketing': 7,
        'personalized ads': 8,
        'targeted ads': 9,
        
        # نقل البيانات دولياً
        'international transfer': 7,
        'cross-border': 7,
        'outside your country': 6,
    }
    
    # ============================================
    # قائمة الكلمات التي تقلل الخطر (موسعة)
    # ============================================
    low_risk_words = {
        # الأمان
        'encrypt': -5,
        'encryption': -5,
        'secure': -3,
        'security': -3,
        'anonymize': -4,
        'anonymization': -4,
        'pseudonymous': -3,
        
        # حقوق المستخدم
        'delete': -4,
        'deletion': -4,
        'opt-out': -6,
        'opt out': -6,
        'unsubscribe': -4,
        'right to access': -5,
        'access your data': -5,
        'right to rectification': -4,
        'right to erasure': -6,
        'right to be forgotten': -6,
        'data portability': -5,
        'object to': -4,
        'withdraw consent': -5,
        
        # الموافقة
        'consent': -4,
        'explicit consent': -5,
        'opt-in': -4,
        'opt in': -4,
        
        # الامتثال القانوني
        'gdpr': -5,
        'ccpa': -5,
        'data protection': -3,
        'privacy policy': -1,
        'data protection officer': -3,
        'dpo': -3,
    }
    
    # تطبيق كلمات الخطر
    for word, points in high_risk_words.items():
        if word in text_lower:
            score += points
            print(f"⚠️ وجدنا كلمة خطرة: '{word}' (+{points})")
    
    # تطبيق كلمات الأمان
    for word, points in low_risk_words.items():
        if word in text_lower:
            score += points  # points سالبة
            print(f"✅ وجدنا كلمة إيجابية: '{word}' ({points})")
    
    # تأكد أن النتيجة بين 0 و 100
    score = max(0, min(100, score))
    
    # ============================================
    # استخراج المخاطر المحددة
    # ============================================
    risks = []
    
    risk_patterns = [
        (r'share.*(third party|third[ -]parties)', 'مشاركة البيانات مع أطراف ثالثة'),
        (r'sell.*(personal|user) data', 'بيع البيانات الشخصية'),
        (r'location|gps', 'جمع بيانات الموقع'),
        (r'track|monitor|analyze.*behavior', 'تتبع نشاط المستخدم'),
        (r'retain.*indefinitely|as long as necessary', 'الاحتفاظ بالبيانات إلى أجل غير مسمى'),
        (r'biometric|fingerprint|face', 'جمع بيانات بيومترية حساسة'),
        (r'health|medical', 'جمع بيانات صحية حساسة'),
        (r'financial|credit card|payment', 'جمع بيانات مالية'),
        (r'browsing history|search history', 'تتبع سجل التصفح'),
        (r'contacts|address book', 'جمع جهات الاتصال'),
        (r'advertising|marketing', 'استخدام البيانات للأغراض التسويقية'),
        (r'third[ -]party.*(advertising|marketing)', 'مشاركة البيانات لأغراض تسويقية'),
        (r'international.*transfer|cross[ -]border', 'نقل البيانات خارج الحدود'),
        (r'children.*under 13', 'جمع بيانات أطفال دون حماية كافية'),
        (r'without.*notice|change.*policy.*without notice', 'تغيير السياسة دون إشعار مسبق'),
        (r'no.*encryption|not.*encrypt', 'عدم استخدام التشفير لحماية البيانات'),
    ]
    
    for pattern, risk_text in risk_patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            risks.append(risk_text)
    
    # ============================================
    # استخراج التفاصيل الإضافية
    # ============================================
    details = {
        'data_collected': [],
        'third_parties': False,
        'retention_period': 'غير محدد',
        'user_rights': False,
        'security_measures': []
    }
    
    # أنواع البيانات المجمعة
    data_types = [
        'name', 'email', 'phone', 'address',
        'location', 'contacts', 'photos', 'messages',
        'browsing history', 'search history',
        'health', 'medical', 'biometric', 'fingerprint',
        'financial', 'payment', 'credit card'
    ]
    
    for data_type in data_types:
        if data_type in text_lower:
            details['data_collected'].append(data_type)
    
    # وجود أطراف ثالثة
    if re.search(r'third[ -]party|third[ -]parties', text_lower, re.IGNORECASE):
        details['third_parties'] = True
    
    # مدة الاحتفاظ
    retention_match = re.search(r'retain.*for (\d+ (day|month|year)s?)', text_lower, re.IGNORECASE)
    if retention_match:
        details['retention_period'] = retention_match.group(1)
    elif re.search(r'indefinitely|as long as necessary', text_lower, re.IGNORECASE):
        details['retention_period'] = 'غير محدد (ربما إلى الأبد)'
    
    # حقوق المستخدم
    if re.search(r'right to|access your data|delete your data', text_lower, re.IGNORECASE):
        details['user_rights'] = True
    
    # إجراءات أمنية
    security_terms = ['encrypt', 'secure', 'ssl', 'https', 'firewall', 'authentication']
    for term in security_terms:
        if term in text_lower:
            details['security_measures'].append(term)
    
    return score, risks, details


# ============================================
# تشغيل الخادم
# ============================================
if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 خادم تحليل سياسة الخصوصية - النسخة المتقدمة 2.0")
    print("="*60)
    print(f"✅ الخادم يعمل على: http://localhost:5000")
    print(f"✅ للاختبار: http://localhost:5000/health")
    print(f"✅ حالة Gemini: {'نشط' if model else 'غير نشط'}")
    print(f"✅ اضغط Ctrl+C للإيقاف")
    print("="*60 + "\n")
    
    app.run(debug=True, port=5000, host='0.0.0.0')