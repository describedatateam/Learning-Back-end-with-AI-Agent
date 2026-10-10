# اجلب المستخدمين واعرضهم كبطاقات

معظم الصفحات تأخذ بياناتها من API. في JavaScript تطلبها بـ **`fetch`**، وتنتظر الرد بـ **`async` / `await`**.

## النمط

```js
async function loadPosts() {
  const response = await fetch('/api/posts');   // 1. اطلب من الخادم
  if (!response.ok) {                            // 2. أخطاء 404 و500 تصل هنا أيضاً
    showError('Could not load posts');
    return;
  }
  const posts = await response.json();           // 3. اقرأ محتوى JSON
  posts.forEach(renderPost);                     // 4. اعرضه في الصفحة
}
```

أمران يخطئ فيهما كثيرون:

- `fetch` يعطيك **Response** وليس البيانات. استدعِ `await response.json()` لقراءتها.
- `fetch` **لا** يرمي خطأ عند 500. تحقّق من `response.ok` بنفسك.

استخدم `textContent` لوضع بيانات الـ API في الصفحة. أما `innerHTML` فقد يشغّل HTML مخفياً داخل البيانات.

## مهمتك

في الملف `script.js` أكمل الدالة `loadUsers()`:

1. اعرض `Loading...` في `#status`.
2. نفّذ `await fetch('/api/users')`.
3. إذا لم تكن الاستجابة ok، اعرض `Could not load users` في `#status` وتوقّف.
4. اقرأ JSON وأضف `<article class="card">` لكل مستخدم داخل `#users`، والاسم في `<h3>` والبريد في `<p>`.
5. فرّغ `#status` عندما تظهر البطاقات.

لا يوجد خادم حقيقي هنا: `/api/users` هو API للتدريب يرد من داخل متصفحك. اكتب الرسائل الإنجليزية كما هي تماماً، لأن الاختبارات تبحث عنها.
