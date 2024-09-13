# طرق وأدوات للتدريب الفعال على معالج رسومات واحد

يوضح هذا الدليل التقنيات العملية التي يمكنك استخدامها لزيادة كفاءة تدريب النموذج الخاص بك من خلال تحسين استخدام الذاكرة، أو تسريع التدريب، أو كليهما. إذا كنت ترغب في فهم كيفية استخدام وحدة معالجة الرسوميات (GPU) أثناء التدريب، يرجى الرجوع أولاً إلى الدليل المفاهيمي [تشريح تدريب النموذج](model_memory_anatomy). يركز هذا الدليل على التقنيات العملية.

<Tip>

إذا كان لديك إمكانية الوصول إلى جهاز به عدة وحدات معالجة رسوميات (GPUs)، فلا تزال هذه الأساليب صالحة، بالإضافة إلى أنه يمكنك الاستفادة من الأساليب الإضافية الموضحة في قسم [وحدات معالجة الرسوميات (GPU) المتعددة](perf_train_gpu_many).

</Tip>

عند تدريب النماذج الكبيرة، هناك جانبان يجب أخذهما في الاعتبار في نفس الوقت:

* *معدل نقل البيانات/وقت التدريب:* زيادة معدل نقل البيانات (عدد العينات في الثانية) يؤدي إلى تقليل تكلفة التدريب. ويتم تحقيق ذلك بشكل عام من خلال الاستفادة القصوى من وحدة معالجة الرسوميات (GPU) وبالتالي ملء ذاكرة وحدة معالجة الرسوميات (GPU) إلى الحد الأقصى. إذا تجاوز حجم الدفعة المطلوب حدود ذاكرة وحدة معالجة الرسوميات (GPU)، فيمكن لتقنيات تحسين الذاكرة، مثل تراكم التدرجات، أن تساعد في ذلك.

* *أداء النموذج:* ومع ذلك، إذا كان حجم الدفعة المفضل يناسب الذاكرة، فلا يوجد سبب لتطبيق تقنيات تحسين الذاكرة لأنها يمكن أن تبطئ التدريب. مجرد أن يكون المرء قادرًا على استخدام حجم دفعة كبير، لا يعني بالضرورة أنه ينبغي عليه ذلك. كجزء من ضبط المعلمات، يجب عليك تحديد حجم الدفعة الذي يحقق أفضل النتائج ثم تحسين الموارد وفقًا لذلك.

يمكن تصنيف الطرق والأدوات المشمولة في هذا الدليل بناءً على التأثير الذي تحدثه على عملية التدريب:

| الطريقة/الأداة | تحسين سرعة التدريب | تحسين استخدام الذاكرة |
|:------------------------:|:----------------------:|:-------------------------:|
| [اختيار حجم الدفعة](#batch-size-choice) | نعم | نعم |
| [تراكم التدرج](#gradient-accumulation) | لا | نعم |
| [التدقيق التدريجي](#gradient-checkpointing) | لا | نعم |
| [تدريب الدقة المختلطة](#mixed-precision-training) | نعم | ربما* |
| [torch_empty_cache_steps](https://huggingface.co/docs/transformers/main/en/main_classes/trainer#transformers.TrainingArguments.torch_empty_cache_steps) | لا | نعم |
| [اختيار المحسن](#optimizer-choice) | نعم | نعم |
| [التحميل المسبق للبيانات](#data-preloading) | نعم | لا |
| [DeepSpeed Zero](#deepspeed-zero) | لا | نعم |
| [torch.compile](#using-torchcompile) | نعم | لا |
| [ضبط دقيق فعال للمعلمات (PEFT)](#using--peft) | لا | نعم |

<Tip>

*ملاحظة: عند استخدام الدقة المختلطة مع نموذج صغير وحجم دفعة كبير، ستكون هناك بعض الوفورات في الذاكرة ولكن مع نموذج كبير وحجم دفعة صغير، سيكون استخدام الذاكرة أكبر.

</Tip>

يمكنك الجمع بين الطرق المذكورة أعلاه للحصول على تأثير تراكمي. تتوفر هذه التقنيات سواء كنت تقوم بتدريب نموذجك باستخدام [`Trainer`] أو كتابة حلقة PyTorch نقية، وفي هذه الحالة يمكنك [تكوين هذه التحسينات باستخدام Accelerate](#using--accelerate).

إذا لم تؤد هذه الطرق إلى مكاسب كافية، فيمكنك استكشاف الخيارات التالية:
* البحث في بناء حاوية Docker مخصصة خاصة بك مع برامج مسبقة البناء فعالة
* النظر في نموذج يستخدم مزيجًا من الخبراء (MoE)
* تحويل نموذجك إلى BetterTransformer للاستفادة من الاهتمام الأصلي في PyTorch

أخيرًا، إذا لم يكن كل ما سبق كافيًا، حتى بعد التبديل إلى وحدة معالجة رسوميات (GPU) من فئة الخوادم مثل A100، ففكر في الانتقال إلى إعداد وحدة معالجة رسوميات (GPU) متعددة. لا تزال جميع هذه الأساليب صالحة في إعداد وحدة معالجة الرسوميات (GPU) متعددة، بالإضافة إلى أنه يمكنك الاستفادة من تقنيات التوازي الإضافية الموضحة في قسم [وحدات معالجة الرسوميات (GPU) المتعددة](perf_train_gpu_many).

## اختيار حجم الدفعة
## اختيار حجم الدفعة

لتحقيق الأداء الأمثل، ابدأ بتحديد حجم الدفعة المناسب. يُنصح باستخدام أحجام دفعات وعدد عصبونات الإدخال/الإخراج التي تكون من حجم 2^N. غالبًا ما يكون هذا العدد مضاعفًا للرقم 8، ولكنه قد يكون أعلى اعتمادًا على الأجهزة المستخدمة ونوع البيانات dtype المستخدمة في النموذج.

للإشارة، راجع توصية NVIDIA لحساب [عدد عصبونات الإدخال/الإخراج](https://docs.nvidia.com/deeplearning/performance/dl-performance-fully-connected/index.html#input-features) و[حجم الدفعة](https://docs.nvidia.com/deeplearning/performance/dl-performance-fully-connected/index.html#batch-size) للطبقات المتصلة تمامًا (التي تشارك في عمليات الضرب العام للمصفوفات).

تحدد [متطلبات Tensor Core](https://docs.nvidia.com/deeplearning/performance/dl-performance-matrix-multiplication/index.html#requirements-tc) المضاعف بناءً على نوع البيانات dtype والأجهزة المستخدمة. على سبيل المثال، بالنسبة لنوع البيانات fp16، يُنصح باستخدام مضاعفات الرقم 8، إلا إذا كان الأمر يتعلق ببطاقة GPU من نوع A100، وفي هذه الحالة، استخدم مضاعفات 64.

بالنسبة للمعلمات الصغيرة، ضع في اعتبارك أيضًا [آثار التكميم الأبعاد](https://docs.nvidia.com/deeplearning/performance/dl-performance-matrix-multiplication/index.html#dim-quantization). هنا يحدث التبليط ويمكن أن يؤدي المضاعف الصحيح إلى تسريع كبير.

## تجميع التدرجات

تهدف طريقة **تجميع التدرجات** إلى حساب التدرجات على شكل أقسام أصغر بدلاً من حسابها دفعة واحدة للدفعة بأكملها. يتضمن هذا النهج حساب التدرجات بشكل تكراري في دفعات أصغر عن طريق تنفيذ عمليات تمرير للأمام والخلف عبر النموذج وتجميع التدرجات أثناء هذه العملية. بمجرد تجميع عدد كافٍ من التدرجات، يتم تنفيذ خطوة التحسين للنموذج. من خلال استخدام تجميع التدرجات، يصبح من الممكن زيادة **حجم الدفعة الفعال** إلى ما بعد القيود التي تفرضها سعة ذاكرة GPU. ومع ذلك، من المهم ملاحظة أن عمليات التمرير الإضافية للأمام والخلف التي قدمها تجميع التدرجات يمكن أن تبطئ عملية التدريب.

يمكنك تمكين تجميع التدرجات عن طريق إضافة وسيط `gradient_accumulation_steps` إلى [`TrainingArguments`]:

```py
training_args = TrainingArguments(per_device_train_batch_size=1, gradient_accumulation_steps=4, **default_args)
```

في المثال أعلاه، يصبح حجم الدفعة الفعال لديك 4.

أو، استخدم 🤗 Accelerate للتحكم الكامل في حلقة التدريب. ابحث عن مثال 🤗 Accelerate [في الأسفل في هذا الدليل](#using-accelerate).

في حين يُنصح بزيادة استخدام GPU قدر الإمكان، يمكن أن يؤدي ارتفاع عدد خطوات تجميع التدرجات إلى تباطؤ ملحوظ في التدريب. ضع في اعتبارك المثال التالي. لنفترض أن `per_device_train_batch_size=4` بدون تجميع التدرجات يصل إلى حد GPU. إذا كنت ترغب في التدريب باستخدام دفعات بحجم 64، فلا تقم بتعيين `per_device_train_batch_size` إلى 1 و`gradient_accumulation_steps` إلى 64. بدلاً من ذلك، احتفظ بـ `per_device_train_batch_size=4` وقم بتعيين `gradient_accumulation_steps=16`. يؤدي هذا إلى نفس حجم الدفعة الفعال مع الاستفادة بشكل أفضل من موارد GPU المتاحة.

للحصول على معلومات إضافية، يرجى الرجوع إلى معايير حجم الدفعة وتجميع التدرجات لـ [RTX-3090](https://github.com/huggingface/transformers/issues/14608#issuecomment-1004392537) و [A100](https://github.com/huggingface/transformers/issues/15026#issuecomment-1005033957).

## نقاط تفتيش التدرج

قد تواجه بعض النماذج الكبيرة مشكلات في الذاكرة حتى عند تعيين حجم الدفعة إلى 1 واستخدام تجميع التدرجات. ويرجع ذلك إلى وجود مكونات أخرى تتطلب أيضًا مساحة تخزين للذاكرة.

يمكن أن يؤدي حفظ جميع التنشيطات من تمرير الإرسال لحساب التدرجات أثناء تمرير العودة إلى زيادة كبيرة في ذاكرة التخزين المؤقت. والنهج البديل المتمثل في التخلص من التنشيطات وإعادة حسابها عند الحاجة أثناء تمرير العودة، من شأنه أن يؤدي إلى زيادة كبيرة في العبء الحسابي وإبطاء عملية التدريب.

تقدم **نقاط تفتيش التدرج** حلًا وسطًا بين هذين النهجين، حيث تقوم بحفظ التنشيطات المختارة بشكل استراتيجي في جميع أنحاء الرسم البياني الحسابي، بحيث لا يلزم إعادة حساب سوى جزء من التنشيطات للتدرجات. للحصول على شرح متعمق لنقاط تفتيش التدرج، راجع [هذه المقالة الرائعة](https://medium.com/tensorflow/fitting-larger-networks-into-memory-583e3c758ff9).

لتمكين نقاط تفتيش التدرج في [`Trainer`]، قم بتمرير العلامة المقابلة إلى [`TrainingArguments`]:

```py
training_args = TrainingArguments(
    per_device_train_batch_size=1, gradient_accumulation_steps=4, gradient_checkpointing=True, **default_args
)
```

أو، استخدم 🤗 Accelerate - ابحث عن مثال 🤗 Accelerate [في الأسفل في هذا الدليل](#using--accelerate). 

<Tip>

في حين أن نقاط تفتيش التدرج قد تحسن كفاءة الذاكرة، إلا أنها تبطئ التدريب بنسبة 20%.

</Tip>

## التدريب عالي الدقة المختلط

**التدريب عالي الدقة المختلط** هي تقنية تهدف إلى تحسين الكفاءة الحسابية لتدريب النماذج من خلال استخدام تنسيقات رقمية منخفضة الدقة لبعض المتغيرات. تقليديًا، تستخدم معظم النماذج دقة النقطة العائمة 32 بت (fp32 أو float32) لتمثيل ومعالجة المتغيرات. ومع ذلك، لا تحتاج جميع المتغيرات إلى هذا المستوى العالي من الدقة لتحقيق نتائج دقيقة. من خلال تقليل دقة متغيرات معينة إلى تنسيقات رقمية أقل، مثل النقطة العائمة 16 بت (fp16 أو float16)، يمكننا تسريع الحسابات. نظرًا لأن بعض الحسابات تتم في هذا النهج بنصف الدقة، بينما لا تزال بعضها الآخر بدقة كاملة، يُطلق على النهج اسم التدريب عالي الدقة المختلط.

يتم تحقيق التدريب عالي الدقة المختلط في معظم الأحيان باستخدام أنواع بيانات fp16 (float16)، ومع ذلك، توفر بعض بنيات GPU (مثل بنية Ampere) أنواع بيانات bf16 وtf32 (نوع بيانات CUDA الداخلي). تحقق من [مدونة NVIDIA](https://developer.nvidia.com/blog/accelerating-ai-training-with-tf32-tensor-cores/) لمعرفة المزيد عن الاختلافات بين أنواع البيانات هذه.

### fp16

تأتي الميزة الرئيسية للتدريب عالي الدقة المختلط من حفظ التنشيطات بنصف الدقة (fp16). على الرغم من أن التدرجات يتم حسابها أيضًا بنصف الدقة، إلا أنها تتحول مرة أخرى إلى دقة كاملة لخطوة التحسين، لذا لا يتم توفير أي ذاكرة هنا.

في حين أن التدريب عالي الدقة المختلط يؤدي إلى حسابات أسرع، إلا أنه يمكن أن يؤدي أيضًا إلى استخدام المزيد من ذاكرة GPU، خاصة لحجم الدفعات الصغيرة. ويرجع ذلك إلى وجود النموذج الآن على GPU بدقة 16 بت و32 بت (1.5x من النموذج الأصلي على GPU).

لتمكين التدريب عالي الدقة المختلط، قم بتعيين العلامة `fp16` إلى `True`:

```py
training_args = TrainingArguments(per_device_train_batch_size=4, fp16=True, **default_args)
```

إذا كنت تفضل استخدام 🤗 Accelerate، فابحث عن مثال 🤗 Accelerate [في الأسفل في هذا الدليل](#using--accelerate). 

### BF16

إذا كان لديك إمكانية الوصول إلى بنية Ampere أو أحدث، فيمكنك استخدام bf16 للتدريب عالي الدقة المختلط والتقييم. في حين أن دقة bf16 أسوأ من fp16، إلا أن لها نطاق ديناميكي أكبر. في fp16، أكبر رقم يمكن أن تحصل عليه هو `65535` وأي رقم أعلى من ذلك سيؤدي إلى فيض. يمكن أن يكون رقم bf16 كبيرًا مثل `3.39e+38` (!) وهو تقريبًا نفس fp32 - لأن كليهما يستخدم 8 بتات لنطاق الأرقام.

يمكنك تمكين BF16 في 🤗 Trainer باستخدام ما يلي:

```python
training_args = TrainingArguments(bf16=True, **default_args)
```

### TF32
يمكنك تمكين BF16 في 🤗 Trainer باستخدام ما يلي:

```python
training_args = TrainingArguments(bf16=True, **default_args)
```

### TF32

تستخدم بنية Ampere نوع بيانات سحري يسمى tf32. ولديه نفس النطاق الرقمي مثل fp32 (8 بتات)، ولكن بدلاً من 23 بت من الدقة، فإنه يحتوي فقط على 10 بتات (نفس fp16) ويستخدم 19 بتًا فقط في المجموع. إنه "سحري" بمعنى أنه يمكنك استخدام رمز التدريب و/أو الاستدلال fp32 العادي، ومن خلال تمكين دعم tf32، يمكنك الحصول على تحسن في الإنتاجية يصل إلى 3 مرات. كل ما عليك فعله هو إضافة ما يلي إلى رمزك:

```python
import torch
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
```

ستقوم CUDA تلقائيًا بالتبديل إلى استخدام tf32 بدلاً من fp32 حيثما أمكن ذلك، بافتراض أن GPU المستخدمة هي من سلسلة Ampere.

وفقًا لـ [بحث NVIDIA](https://developer.nvidia.com/blog/accelerating-ai-training-with-tf32-tensor-cores/)، فإن غالبية أعباء عمل التدريب على التعلم الآلي تظهر نفس الغموض والتقارب مع التدريب tf32 كما هو الحال مع fp32. إذا كنت تستخدم بالفعل fp16 أو bf16 عالي الدقة المختلط، فقد يساعد ذلك في الإنتاجية أيضًا.

يمكنك تمكين هذا الوضع في 🤗 Trainer:

```python
TrainingArguments(tf32=True, **default_args)
```

<Tip>

لا يمكن الوصول إلى tf32 مباشرة عبر `tensor.to(dtype=torch.tf32)` لأنه نوع بيانات داخلي لـ CUDA. تحتاج إلى `torch>=1.7` لاستخدام أنواع بيانات tf32.

</Tip>

للحصول على معلومات إضافية حول tf32 مقابل الدقة الأخرى، يرجى الرجوع إلى المعايير المرجعية التالية: [RTX-3090](https://github.com/huggingface/transformers/issues/14608#issuecomment-1004390803) و [A100](https://github.com/huggingface/transformers/issues/15026#issuecomment-1004543189).

## Flash Attention 2

يمكنك تسريع إنتاجية التدريب باستخدام تكامل Flash Attention 2 في المحولات. تحقق من القسم المناسب في [قسم GPU الفردي](./perf_infer_gpu_one#Flash-Attention-2) لمعرفة المزيد حول كيفية تحميل نموذج باستخدام وحدات Flash Attention 2. 

## اختيار المحسن

المحسن الأكثر استخدامًا لتدريب نماذج المحول هو Adam أو AdamW (Adam مع انحلال الوزن). يحقق Adam تقاربًا جيدًا عن طريق تخزين المتوسط ​​المتحرك للتدرجات السابقة؛ ومع ذلك، فإنه يضيف بصمة ذاكرة إضافية بحجم عدد معلمات النموذج. لمعالجة ذلك، يمكنك استخدام محسن بديل. على سبيل المثال، إذا كان لديك [NVIDIA/apex](https://github.com/NVIDIA/apex) مثبتًا لـ GPUs من NVIDIA، أو [ROCmSoftwarePlatform/apex](https://github.com/ROCmSoftwarePlatform/apex) لـ GPUs من AMD، فسيمنحك `adamw_apex_fused` أسرع تجربة تدريب بين جميع محسنات AdamW المدعومة.

يتكامل [`Trainer`] مع مجموعة متنوعة من المحسنات التي يمكن استخدامها مباشرة من الصندوق: `adamw_hf`، `adamw_torch`، `adamw_torch_fused`، `adamw_apex_fused`، `adamw_anyprecision`، `adafactor`، أو `adamw_bnb_8bit`. يمكن إضافة محسنات أخرى عبر تنفيذ تابع خارجي.

دعونا نلقي نظرة فاحصة على بديلين لمحسن AdamW:

1. `adafactor` المتاح في [`Trainer`]
2. `adamw_bnb_8bit` متاح أيضًا في Trainer، ولكن يتم توفير تكامل تابع خارجي أدناه للتوضيح.

لمقارنة، لنموذج 3B-parameter، مثل "google-t5/t5-3b": 

* سوف يحتاج محسن AdamW القياسي إلى 24 جيجابايت من ذاكرة GPU لأنه يستخدم 8 بايتات لكل معلمة (8*3 => 24 جيجابايت)
* سوف يحتاج محسن Adafactor إلى أكثر من 12 جيجابايت. يستخدم أكثر بقليل من 4 بايتات لكل معلمة، لذا 4*3 وبعض الإضافات.
* سوف يستخدم محسن 8bit BNB المُدرج 6 جيجابايت فقط إذا تم تكميم جميع حالات المحسن.

### Adafactor

لا يقوم Adafactor بتخزين المتوسطات المتحركة لكل عنصر في مصفوفات الأوزان. بدلاً من ذلك، فإنه يحتفظ بالمعلومات المجمعة (مجاميع المتوسطات المتحركة صفًا وعموديًا)، مما يقلل بشكل كبير من بصمته. ومع ذلك، مقارنة بـ Adam، قد يكون لدى Adafactor تقارب أبطأ في بعض الحالات.

يمكنك التبديل إلى Adafactor عن طريق تعيين `optim="adafactor"` في [`TrainingArguments`]:

```py
training_args = TrainingArguments(per_device_train_batch_size=4, optim="adafactor"، **default_args)
```

بالجمع بين النُهج الأخرى (تجميع التدرجات، ونقاط تفتيش التدرج، والتدريب عالي الدقة المختلط)، يمكنك ملاحظة تحسن يصل إلى 3 مرات مع الحفاظ على الإنتاجية! ومع ذلك، كما ذكرنا سابقًا، قد يكون تقارب Adafactor أسوأ من Adam. 

### Adam 8-بت

بدلاً من تجميع حالات المحسن مثل Adafactor، يحتفظ Adam 8-بت بالحالة الكاملة ويقوم بتكميمها. يعني التكميم أنه يتم تخزين الحالة بدقة أقل ويتم إلغاء تكميمها فقط للتحسين. هذا مشابه لفكرة التدريب عالي الدقة المختلط.

لاستخدام `adamw_bnb_8bit`، ما عليك سوى تعيين `optim="adamw_bnb_8bit"` في [`TrainingArguments`]:

```py
training_args = TrainingArguments(per_device_train_batch_size=4, optim="adamw_bnb_8bit"، **default_args)
```

ومع ذلك، يمكننا أيضًا استخدام تنفيذ تابع خارجي لمحسن 8 بت للتوضيح.

أولاً، اتبع دليل التثبيت في مستودع [GitHub](https://github.com/TimDettmers/bitsandbytes) لتثبيت مكتبة `bitsandbytes` التي تنفذ محسن Adam 8 بت.

بعد ذلك، تحتاج إلى تهيئة المحسن. ينطوي ذلك على خطوتين:

* أولاً، قم بتقسيم معلمات النموذج إلى مجموعتين - واحدة يتم تطبيق انحلال الوزن عليها، والأخرى لا يتم تطبيقه عليها. عادةً ما يتم تطبيق انحلال الوزن على معلمات التحيز ومعلمات طبقة التطبيع.
* ثم قم بتنظيف وسيطات المحسن لاستخدام نفس المعلمات مثل محسن AdamW المستخدم سابقًا.

```py
import bitsandbytes as bnb
from torch import nn
from transformers.trainer_pt_utils import get_parameter_names

training_args = TrainingArguments(per_device_train_batch_size=4, **default_args)

decay_parameters = get_parameter_names(model, [nn.LayerNorm])
decay_parameters = [name for name in decay_parameters if "bias" not in name]
optimizer_grouped_parameters = [
    {
        "params": [p for n, p in model.named_parameters() if n in decay_parameters],
        "weight_decay": training_args.weight_decay,
    },
    {
        "params": [p for n, p in model.named_parameters() if n not in decay_parameters],
        "weight_decay": 0.0,
    },
]

optimizer_kwargs = {
    "betas": (training_args.adam_beta1, training_args.adam_beta2),
    "eps": training_args.adam_epsilon,
}
optimizer_kwargs["lr"] = training_args.learning_rate
adam_bnb_optim = bnb.optim.Adam8bit(
    optimizer_grouped_parameters,
    betas=(training_args.adam_beta1, training_args.adam_beta2),
    eps=training_args.adam_epsilon,
    lr=training_args.learning_rate,
)
```
أخيرًا، قم بتمرير المحسن المخصص كحجة إلى "Trainer":

```py
trainer = Trainer(model=model, args=training_args, train_dataset=ds, optimizers=(adam_bnb_optim, None))
```

بالجمع بين هذا النهج ونهج أخرى (تجميع الخرجات، وحفظ نقاط التفتيش للخرجات، والتدريب على الدقة المختلطة)، يمكنك توقع تحسن في الذاكرة بحوالي 3 مرات، وحتى زيادة طفيفة في الإنتاجية مقارنة باستخدام Adafactor.

### multi_tensor

قدم pytorch-nightly `torch.optim._multi_tensor` الذي يجب أن يسرع بشكل كبير المحسنات في الحالات التي تحتوي على العديد من تنسيقات الميزات الصغيرة. ومن المتوقع أن يصبح هو الوضع الافتراضي، ولكن إذا كنت تريد تجربته في وقت أقرب، فراجع مشكلة GitHub [هذه](https://github.com/huggingface/transformers/issues/9965).

## التحميل المسبق للبيانات

أحد المتطلبات المهمة للوصول إلى سرعة تدريب عالية هي القدرة على تغذية وحدة معالجة الرسومات (GPU) بأقصى سرعة يمكنها التعامل معها. بشكل افتراضي، يحدث كل شيء في العملية الرئيسية، وقد لا تتمكن من قراءة البيانات من القرص بسرعة كافية، مما يؤدي إلى اختناق، مما يؤدي إلى الاستخدام الناقص لوحدة معالجة الرسومات (GPU). قم بتكوين الحجج التالية لتقليل الاختناق:

- `DataLoader(pin_memory=True, ...)` - يضمن تحميل البيانات مسبقًا في الذاكرة المثبتة على وحدة المعالجة المركزية (CPU) وعادة ما يؤدي إلى نقل أسرع بكثير من ذاكرة وحدة المعالجة المركزية (CPU) إلى ذاكرة وحدة معالجة الرسومات (GPU).
- `DataLoader(num_workers=4, ...)` - قم بتشغيل العديد من العمال لتحميل البيانات بشكل أسرع. أثناء التدريب، راقب إحصائيات استخدام وحدة معالجة الرسومات (GPU)؛ إذا كان أقل من 100%، فجرّب زيادة عدد العمال. بالطبع، قد تكون المشكلة في مكان آخر، لذا فإن العديد من العمال لن يؤدي بالضرورة إلى أداء أفضل.

عند استخدام [`Trainer`]، تكون الحجج المقابلة [`TrainingArguments`] هي: `dataloader_pin_memory` (`True` بشكل افتراضي)، و`dataloader_num_workers` (افتراضيًا `0`).

## DeepSpeed ZeRO

DeepSpeed هي مكتبة تحسين للتعلم العميق مفتوحة المصدر مدمجة في 🤗 Transformers و 🤗 Accelerate. فهو يوفر مجموعة واسعة من الميزات والتحسينات المصممة لتحسين كفاءة وقابلية توسع التدريب على التعلم العميق واسع النطاق.

إذا كان نموذجك يناسب وحدة معالجة رسومات (GPU) واحدة ولديك مساحة كافية لتناسب حجم دفعة صغير، فلا تحتاج إلى استخدام DeepSpeed لأنه سيبطئ الأمور فقط. ومع ذلك، إذا لم يناسب النموذج وحدة معالجة رسومات (GPU) واحدة أو لا يمكنك تناسب حجم دفعة صغير، فيمكنك الاستفادة من DeepSpeed ZeRO + CPU Offload، أو NVMe Offload للنماذج الأكبر بكثير. في هذه الحالة، تحتاج إلى [تثبيت المكتبة](main_classes/deepspeed#installation) بشكل منفصل، ثم اتبع أحد الأدلة لإنشاء ملف تكوين وتشغيل DeepSpeed:

* للحصول على دليل متعمق حول تكامل DeepSpeed مع [`Trainer`]، راجع [التوثيق المقابل](main_classes/deepspeed)، وتحديدًا [القسم الخاص بوحدة معالجة رسومات (GPU) واحدة](main_classes/deepspeed#deployment-with-one-gpu). مطلوب بعض التعديلات لاستخدام DeepSpeed في دفتر ملاحظات؛ يرجى إلقاء نظرة على [الدليل المقابل](main_classes/deepspeed#deployment-in-notebooks).
* إذا كنت تفضل استخدام 🤗 Accelerate، يرجى الرجوع إلى [دليل DeepSpeed في 🤗 Accelerate](https://huggingface.co/docs/accelerate/en/usage_guides/deepspeed).

## استخدام torch.compile

قدم PyTorch 2.0 دالة تجميع جديدة لا تتطلب أي تعديل على تعليمات PyTorch البرمجية الحالية ولكن يمكنها تحسين تعليمات PyTorch البرمجية الخاصة بك عن طريق إضافة سطر واحد من التعليمات البرمجية: `model = torch.compile(model)`.

إذا كنت تستخدم [`Trainer`]، فيجب عليك فقط تمرير `to` خيار `torch_compile` في [`TrainingArguments`]:

```python
training_args = TrainingArguments(torch_compile=True, **default_args)
```

يستخدم `torch.compile` واجهة برمجة تطبيقات تقييم الإطار في Python لإنشاء رسم بياني تلقائيًا من برامج PyTorch الموجودة. بعد التقاط الرسم البياني، يمكن نشر backends مختلفة لخفض الرسم البياني إلى محرك محسّن. يمكنك العثور على مزيد من التفاصيل والاختبارات المعيارية في [وثائق PyTorch](https://pytorch.org/get-started/pytorch-2.0/).

لدى `torch.compile` قائمة متزايدة من backends، والتي يمكن العثور عليها عن طريق استدعاء `torchdynamo.list_backends()`، لكل منها تبعياته الاختيارية.

حدد backend الذي سيتم استخدامه عن طريق تحديده عبر `torch_compile_backend` في [`TrainingArguments`]. بعض backends الأكثر استخدامًا هي:

**backends التصحيح**:
* `dynamo.optimize("eager")` - يستخدم PyTorch لتشغيل GraphModule المستخرج. هذا مفيد جدًا في تصحيح مشكلات TorchDynamo.
* `dynamo.optimize("aot_eager")` - يستخدم AotAutograd بدون مترجم، أي مجرد استخدام PyTorch eager لرسوم forward وbackward في AotAutograd. هذا مفيد للتصحيح، ومن غير المرجح أن يوفر تسريعًا.

**backends التدريب والاستدلال**:
* `dynamo.optimize("inductor")` - يستخدم backend TorchInductor مع AotAutograd وcudagraphs عن طريق الاستفادة من نواة Triton codegened [اقرأ المزيد](https://dev-discuss.pytorch.org/t/torchinductor-a-pytorch-native-compiler-with-define-by-run-ir-and-symbolic-shapes/747)
* `dynamo.optimize("nvfuser")` - nvFuser مع TorchScript. [اقرأ المزيد](https://dev-discuss.pytorch.org/t/tracing-with-primitives-update-1-nvfuser-and-its-primitives/593)
* `dynamo.optimize("aot_nvfuser")` - nvFuser مع AotAutograd. [اقرأ المزيد](https://dev-discuss.pytorch.org/t/tracing-with-primitives-update-1-nvfuser-and-its-primitives/593)
* `dynamo.optimize("aot_cudagraphs")` - cudagraphs مع AotAutograd. [اقرأ المزيد](https://github.com/pytorch/torchdynamo/pull/757)

**backends الاستدلال فقط**:
* `dynamo.optimize("ofi")` - يستخدم Torchscript optimize_for_inference. [اقرأ المزيد](https://pytorch.org/docs/stable/generated/torch.jit.optimize_for_inference.html)
* `dynamo.optimize("fx2trt")` - يستخدم NVIDIA TensorRT لتحسين الاستدلال. [اقرأ المزيد](https://pytorch.org/TensorRT/tutorials/getting_started_with_fx_path.html)
* `dynamo.optimize("onnxrt")` - يستخدم ONNXRT للاستدلال على وحدة المعالجة المركزية (CPU) / وحدة معالجة الرسومات (GPU). [اقرأ المزيد](https://onnxruntime.ai/)
* `dynamo.optimize("ipex")` - يستخدم IPEX للاستدلال على وحدة المعالجة المركزية (CPU). [اقرأ المزيد](https://github.com/intel/intel-extension-for-pytorch)

لمثال على استخدام `torch.compile` مع 🤗 Transformers، تحقق من [منشور المدونة حول ضبط نموذج BERT الدقيق لتصنيف النصوص باستخدام أحدث ميزات PyTorch 2.0](https://www.philschmid.de/getting-started-pytorch-2-0-transformers)

## استخدام PEFT (ضبط دقيق فعال من حيث التكلفة)

تقوم طرق [ضبط دقيق فعال من حيث التكلفة للمعلمات](https://huggingface.co/blog/peft) بتجميد معلمات النموذج المُدرب مسبقًا أثناء الضبط الدقيق وإضافة عدد صغير من المعلمات القابلة للتدريب (المهايئات) فوقه.

ونتيجة لذلك، يتم تقليل [الذاكرة المرتبطة بحالات المُحسن والتدرجات](https://huggingface.co/docs/transformers/model_memory_anatomy#anatomy-of-models-memory) بشكل كبير.

على سبيل المثال، باستخدام AdamW الفانيلا، سيكون متطلب الذاكرة لحالة المُحسن كما يلي:

- نسخة fp32 من المعلمات: 4 بايت/معلمة
- الزخم: 4 بايت/معلمة
- التباين: 4 بايت/معلمة

لنفترض أن لدينا نموذجًا به 7 مليارات معلمة و200 مليون معلمة تم حقنها باستخدام [محولات الترتيب المنخفض](https://huggingface.co/docs/peft/conceptual_guides/lora).

سيكون متطلب الذاكرة لحالة المُحسن للنموذج العادي 12 * 7 = 84 جيجابايت (بافتراض 7 مليارات معلمة قابلة للتدريب).

تؤدي إضافة Lora إلى زيادة طفيفة في الذاكرة المرتبطة بأوزان النموذج وتقليل متطلبات الذاكرة لحالة المُحسن بشكل كبير إلى 12 * 0.2 = 2.4 جيجابايت.

لمعرفة المزيد حول PEFT واستخدامه المفصل، راجع [وثائق PEFT](https://huggingface.co/docs/peft/) أو [مستودع PEFT](https://github.com/huggingface/peft).

## استخدام 🤗 Accelerate

مع [🤗 Accelerate](https://huggingface.co/docs/accelerate/index)، يمكنك استخدام الطرق المذكورة أعلاه مع التحكم الكامل في حلقة التدريب، ويمكنك أساسيًا كتابة الحلقة في PyTorch النقي مع بعض التعديلات الطفيفة.

لنفترض أنك قمت بدمج الطرق في [`TrainingArguments`] كما يلي:

```py
training_args = TrainingArguments(
    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,
    gradient_checkpointing=True,
    fp16=True,
    **default_args,
)
```

تتكون حلقة التدريب الكاملة باستخدام 🤗 Accelerate من بضع أسطر فقط من التعليمات البرمجية:

```py
from accelerate import Accelerator
from torch.utils.data.dataloader import DataLoader

dataloader = DataLoader(ds, batch_size=training_args.per_device_train_batch_size)

if training_args.gradient_checkpointing:
    model.gradient_checkpointing_enable()

accelerator = Accelerator(fp16=training_args.fp16)
model, optimizer, dataloader = accelerator.prepare(model, adam_bnb_optim, dataloader)
accelerator = Accelerator(fp16=training_args.fp16)
model, optimizer, dataloader = accelerator.prepare(model, adam_bnb_optim, dataloader)

model.train()
for step, batch in enumerate(dataloader, start=1):
    loss = model(**batch).loss
    loss = loss / training_args.gradient_accumulation_steps
    accelerator.backward(loss)
    if step % training_args.gradient_accumulation_steps == 0:
        optimizer.step()
        optimizer.zero_grad()
```

أولاً، نقوم بتغليف مجموعة البيانات في [`DataLoader`](https://pytorch.org/docs/stable/data.html#torch.utils.data.DataLoader).
بعد ذلك، يمكننا تمكين التحقق من التدرج عن طريق استدعاء طريقة [`~PreTrainedModel.gradient_checkpointing_enable`] للنموذج.
عند تهيئة [`Accelerator`](https://huggingface.co/docs/accelerate/package_reference/accelerator#accelerate.Accelerator)،
يمكننا تحديد ما إذا كنا نريد استخدام التدريب بالدقة المختلطة، وسيتولى الأمر نيابة عنا في مكالمة [`prepare`].
أثناء مكالمة [`prepare`](https://huggingface.co/docs/accelerate/package_reference/accelerator#accelerate.Accelerator.prepare)،
سيتم أيضًا توزيع برنامج التغذية التلقائية عبر العمال في حالة استخدام وحدات معالجة الرسومات (GPU) متعددة. نستخدم نفس [محسن 8 بت](#8-bit-adam) من المثال السابق.

أخيرًا، يمكننا إضافة حلقة التدريب الرئيسية. لاحظ أن مكالمة `backward` تتم من خلال 🤗 Accelerate. يمكننا أيضًا أن نرى
كيف يعمل تراكم التدرجات: نقوم بتطبيع الخسارة، لذلك نحصل على المتوسط في نهاية التراكم وبمجرد أن يكون لدينا
خطوات كافية، نقوم بتشغيل التحسين.

لا يتطلب تنفيذ تقنيات التحسين هذه باستخدام 🤗 Accelerate سوى بضع أسطر من التعليمات البرمجية وتأتي بميزة المرونة في حلقة التدريب. للحصول على وثائق كاملة لجميع الميزات، راجع [وثائق Accelerate](https://huggingface.co/docs/accelerate/index).

## البرامج الفعالة مسبقة البناء

تأتي إصدارات PyTorch [pip وconda](https://pytorch.org/get-started/locally/#start-locally) مُجمَّعة مسبقًا مع حزمة CUDA toolkit
التي تكون كافية لتشغيل PyTorch، ولكنها غير كافية إذا كنت بحاجة إلى إنشاء ملحقات CUDA.

في بعض الأحيان، قد تكون هناك حاجة إلى بذل جهود إضافية لبناء بعض المكونات مسبقًا. على سبيل المثال، إذا كنت تستخدم مكتبات مثل `apex` التي
لا تأتي مجمعة مسبقًا. في مواقف أخرى، قد يكون من الصعب معرفة كيفية تثبيت حزمة CUDA toolkit على مستوى النظام.
لمعالجة هذه السيناريوهات، أصدرت PyTorch وNVIDIA إصدارًا جديدًا من حاوية NGC docker التي تأتي بالفعل مع
كل شيء مُجمَّع مسبقًا. ما عليك سوى تثبيت برامجك عليه، وسيعمل على الفور.

هذا النهج مفيد أيضًا إذا كنت تريد ضبط مصدر pytorch و/أو إجراء بناء مخصص جديد.
لعثور على إصدار صورة docker الذي تريده، ابدأ [بملاحظات إصدار PyTorch](https://docs.nvidia.com/deeplearning/frameworks/pytorch-release-notes/)،
واختر أحدث الإصدارات الشهرية. انتقل إلى ملاحظات الإصدار للنسخة المطلوبة، وتحقق من أن مكونات البيئة تتطابق مع احتياجاتك (بما في ذلك متطلبات برنامج تشغيل NVIDIA!) ثم في أعلى تلك الوثيقة، انتقل
إلى صفحة NGC المقابلة. إذا ضللت الطريق لسبب ما، فهذا هو [فهرس جميع صور NGC PyTorch](https://ngc.nvidia.com/catalog/containers/nvidia:pytorch).

بعد ذلك، اتبع التعليمات لتنزيل صورة docker ونشرها.

## مزيج من الخبراء

أبلغت بعض الأوراق البحثية الحديثة عن زيادة سرعة التدريب بمقدار 4-5 مرات وزيادة سرعة الاستدلال عن طريق دمج
مزيج من الخبراء (MoE) في نماذج المحول.

نظرًا لاكتشاف أن المزيد من المعلمات يؤدي إلى أداء أفضل، تسمح هذه التقنية بزيادة
عدد المعلمات بمقدار درجة دون زيادة تكاليف التدريب.

في هذا النهج، يتم استبدال كل طبقة شبكة عصبية اصطناعية أخرى بطبقة MoE تتكون من العديد من الخبراء، مع دالة بوابة
تدرب كل خبير بطريقة متوازنة اعتمادًا على موضع رمز الإدخال في تسلسل.
![محول MoE 2x block](https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/perf-moe-transformer.png)

(المصدر: [GLAM](https://ai.googleblog.com/2021/12/more-efficient-in-context-learning-with.html))

يمكنك العثور على تفاصيل شاملة وجداول مقارنة في الأوراق البحثية المدرجة في نهاية هذا القسم.

الجانب السلبي الرئيسي لهذا النهج هو أنه يتطلب كميات هائلة من ذاكرة GPU - أكبر بحوالي درجة من مكافئها الكثيف. تم اقتراح تقطير ونهج مختلفة للتغلب على متطلبات الذاكرة الأعلى بكثير.

هناك مقايضة مباشرة، فيمكنك استخدام عدد قليل من الخبراء مع نموذج أساسي أصغر بمقدار 2-3 مرات بدلاً من عشرات أو
مئات الخبراء مما يؤدي إلى نموذج أصغر بمقدار 5 مرات وبالتالي زيادة سرعة التدريب بشكل معتدل مع زيادة
متطلبات الذاكرة بشكل معتدل أيضًا.

تم بناء معظم الأوراق البحثية والتنفيذات ذات الصلة حول Tensorflow/TPUs:

- [GShard: Scaling Giant Models with Conditional Computation and Automatic Sharding](https://arxiv.org/abs/2006.16668)
- [Switch Transformers: Scaling to Trillion Parameter Models with Simple and Efficient Sparsity](https://arxiv.org/abs/2101.03961)
- [GLaM: Generalist Language Model (GLaM)](https://ai.googleblog.com/2021/12/more-efficient-in-context-learning-with.html)

وبالنسبة لـ Pytorch، فقد قامت DeepSpeed ببنائه أيضًا: [DeepSpeed-MoE: Advancing Mixture-of-Experts Inference and Training to Power Next-Generation AI Scale](https://arxiv.org/abs/2201.05596)، [Mixture of Experts](https://www.deepspeed.ai/tutorials/mixture-of-experts/) - منشورات المدونة: [1](https://www.microsoft.com/en-us/research/blog/deepspeed-powers-8x-larger-moe-model-training-with-high-performance/)، [2](https://www.microsoft.com/en-us/research/publication/scalable-and-efficient-moe-training-for-multitask-multilingual-models/) والنشر المحدد مع نماذج توليد اللغة الطبيعية الكبيرة القائمة على المحول: [منشور المدونة](https://www.deepspeed.ai/2021/12/09/deepspeed-moe-nlg.html)، [فرع Megatron-Deepspeed](https://github.com/microsoft/Megatron-DeepSpeed/tree/moe-training).

## استخدام PyTorch native attention وFlash Attention

يمكن لـ PyTorch [`torch.nn.functional.scaled_dot_product_attention`](https://pytorch.org/docs/master/generated/torch.nn.functional.scaled_dot_product_attention.html) (SDPA) أيضًا استدعاء FlashAttention واهتمامات فعالة من حيث الذاكرة في الخلفية. يجري حاليًا إضافة دعم SDPA بشكل أصلي في Transformers ويتم استخدامه بشكل افتراضي لـ `torch>=2.1.1` عند توفر التنفيذ. يرجى الرجوع إلى [اهتمام PyTorch بمُنتج النقاط المُدرج](https://huggingface.co/docs/transformers/perf_infer_gpu_one#pytorch-scaled-dot-product-attention) للحصول على قائمة بالنماذج المدعومة والمزيد من التفاصيل.

تفقد هذا [المنشور](https://pytorch.org/blog/out-of-the-box-acceleration/) لمعرفة المزيد حول التسريع ووفورات الذاكرة باستخدام SDPA.