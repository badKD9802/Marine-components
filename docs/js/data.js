// js/data.js 파일

// API base URL (Railway production server)
const API_BASE = 'https://marine-parts-production-60a3.up.railway.app';

// Fallback data (used when API is unavailable)
const fallbackProducts = [
    {
        id: 1,
        image: "./parts_image/YANMAR CON BOD BEARING(4TNV98 129900-23600).jpg",
        partNo: "4TNV98 129900-23600",
        price: "2,000",
        name: { ko: "얀마 커넥팅 로드 베어링", en: "YANMAR CON ROD BEARING", cn: "YANMAR 连杆轴承" },
        desc: { ko: "4TNV98 엔진 호환", en: "Compatible with 4TNV98", cn: "兼容 4TNV98" },
        brand: "YANMAR",
        category: "bearing",
        categoryName: { ko: "베어링", en: "Bearing", cn: "轴承" },
        detailInfo: {
            ko: "YANMAR 4TNV98 엔진에 사용되는 고품질 커넥팅 로드 베어링입니다. 정밀 가공으로 엔진 내구성과 성능을 보장하며, 순정품과 동일한 규격으로 제작되었습니다. 장기간 안정적인 운전을 위한 필수 교체 부품입니다.",
            en: "High-quality connecting rod bearing for YANMAR 4TNV98 engines. Precision-machined to ensure engine durability and performance, manufactured to OEM specifications. An essential replacement part for long-term stable operation.",
            cn: "适用于YANMAR 4TNV98发动机的高品质连杆轴承。精密加工确保发动机耐久性和性能，按OEM规格制造。是长期稳定运行的必备更换零件。"
        },
        specs: {
            ko: { "부품번호": "4TNV98 129900-23600", "브랜드": "YANMAR", "카테고리": "베어링", "호환 엔진": "4TNV98", "상태": "신품", "원산지": "일본" },
            en: { "Part Number": "4TNV98 129900-23600", "Brand": "YANMAR", "Category": "Bearing", "Compatible Engine": "4TNV98", "Condition": "New", "Origin": "Japan" },
            cn: { "零件编号": "4TNV98 129900-23600", "品牌": "YANMAR", "类别": "轴承", "兼容发动机": "4TNV98", "状态": "全新", "产地": "日本" }
        },
        compatibility: {
            ko: ["YANMAR 4TNV98 시리즈", "YANMAR 4TNV98T 터보"],
            en: ["YANMAR 4TNV98 Series", "YANMAR 4TNV98T Turbo"],
            cn: ["YANMAR 4TNV98 系列", "YANMAR 4TNV98T 涡轮"]
        }
    },
    {
        id: 2,
        image: "./parts_image/YANMAR EY18AL.jpg",
        partNo: "PB1002 / PB1003",
        price: "400,000",
        name: { ko: "마린 디젤 엔진 플런저 베럴", en: "YANMAR EY18AL Plunger", cn: "YANMAR EY18AL 柱塞" },
        desc: { ko: "AL-SERIES / AL-PLUS 모델", en: "AL-SERIES / AL-PLUS", cn: "AL-SERIES / AL-PLUS" },
        brand: "YANMAR",
        category: "plunger",
        categoryName: { ko: "플런저", en: "Plunger", cn: "柱塞" },
        detailInfo: {
            ko: "YANMAR EY18AL 엔진용 연료 분사 플런저 베럴입니다. AL-SERIES 및 AL-PLUS 모델에 호환되며, 정밀한 연료 분사를 통해 엔진 효율을 극대화합니다. 고내구성 소재로 장시간 사용에도 안정적인 성능을 유지합니다.",
            en: "Fuel injection plunger barrel for YANMAR EY18AL engines. Compatible with AL-SERIES and AL-PLUS models, maximizing engine efficiency through precise fuel injection. Made with high-durability materials for reliable performance over extended use.",
            cn: "适用于YANMAR EY18AL发动机的燃油喷射柱塞筒。兼容AL-SERIES和AL-PLUS型号，通过精确燃油喷射最大化发动机效率。采用高耐久性材料，长时间使用仍保持稳定性能。"
        },
        specs: {
            ko: { "부품번호": "PB1002 / PB1003", "브랜드": "YANMAR", "카테고리": "플런저", "호환 모델": "EY18AL, AL-SERIES, AL-PLUS", "상태": "신품", "원산지": "일본" },
            en: { "Part Number": "PB1002 / PB1003", "Brand": "YANMAR", "Category": "Plunger", "Compatible Model": "EY18AL, AL-SERIES, AL-PLUS", "Condition": "New", "Origin": "Japan" },
            cn: { "零件编号": "PB1002 / PB1003", "品牌": "YANMAR", "类别": "柱塞", "兼容型号": "EY18AL, AL-SERIES, AL-PLUS", "状态": "全新", "产地": "日本" }
        },
        compatibility: {
            ko: ["YANMAR EY18AL", "YANMAR AL-SERIES", "YANMAR AL-PLUS"],
            en: ["YANMAR EY18AL", "YANMAR AL-SERIES", "YANMAR AL-PLUS"],
            cn: ["YANMAR EY18AL", "YANMAR AL-SERIES", "YANMAR AL-PLUS"]
        }
    },
    {
        id: 3,
        image: "./parts_image/DAIHATSU,KASAKA,YAN MAR,HANSHIN MAN,Etc.jpg",
        partNo: "Multi-Brand Parts",
        price: "문의 (Contact Us)",
        name: { ko: "선박 엔진 예비 부품 모음", en: "Marine Spare Parts (Daihatsu, Yanmar...)", cn: "船用备件 (Daihatsu, Yanmar...)" },
        desc: { ko: "다이하츠, 얀마, 한신 등 취급", en: "Daihatsu, Yanmar, Hanshin etc.", cn: "Daihatsu, Yanmar, Hanshin 等" },
        brand: "Multi-Brand",
        category: "spare",
        categoryName: { ko: "예비부품", en: "Spare Parts", cn: "备件" },
        detailInfo: {
            ko: "Daihatsu, YANMAR, Hanshin, MAN 등 다양한 브랜드의 선박 엔진 예비 부품을 종합적으로 취급합니다. 피스톤, 라이너, 베어링, 밸브, 가스켓 등 주요 부품을 재고 보유하고 있으며, 대량 구매 시 특별 가격을 제공합니다.",
            en: "Comprehensive range of marine engine spare parts from various brands including Daihatsu, YANMAR, Hanshin, and MAN. We stock key components such as pistons, liners, bearings, valves, and gaskets, with special pricing available for bulk orders.",
            cn: "综合经营Daihatsu、YANMAR、Hanshin、MAN等多品牌船用发动机备件。库存主要零部件包括活塞、缸套、轴承、阀门、垫片等，大量采购可享受特别价格。"
        },
        specs: {
            ko: { "부품번호": "Multi-Brand Parts", "브랜드": "Daihatsu, YANMAR, Hanshin, MAN 외", "카테고리": "예비부품 종합", "취급 부품": "피스톤, 라이너, 베어링, 밸브, 가스켓 등", "상태": "신품 / 리빌드", "원산지": "다국적" },
            en: { "Part Number": "Multi-Brand Parts", "Brand": "Daihatsu, YANMAR, Hanshin, MAN etc.", "Category": "Comprehensive Spare Parts", "Parts Handled": "Pistons, Liners, Bearings, Valves, Gaskets etc.", "Condition": "New / Rebuilt", "Origin": "Multinational" },
            cn: { "零件编号": "Multi-Brand Parts", "品牌": "Daihatsu, YANMAR, Hanshin, MAN 等", "类别": "综合备件", "经营零件": "活塞、缸套、轴承、阀门、垫片等", "状态": "全新 / 翻新", "产地": "多国" }
        },
        compatibility: {
            ko: ["Daihatsu 전 시리즈", "YANMAR 전 시리즈", "Hanshin 전 시리즈", "MAN B&W 시리즈"],
            en: ["Daihatsu All Series", "YANMAR All Series", "Hanshin All Series", "MAN B&W Series"],
            cn: ["Daihatsu 全系列", "YANMAR 全系列", "Hanshin 全系列", "MAN B&W 系列"]
        }
    },
    {
        id: 4,
        image: "./parts_image/E205250040Z.jpg",
        partNo: "E205250040Z",
        price: "100,000",
        name: { ko: "피스톤 핀 부시", en: "Piston Pin Bush", cn: "活塞销衬套" },
        desc: { ko: "해양 엔진 부품", en: "Marine Engine Parts", cn: "船用发动机零件" },
        brand: "OEM",
        category: "piston",
        categoryName: { ko: "피스톤", en: "Piston", cn: "活塞" },
        detailInfo: {
            ko: "해양 디젤 엔진에 사용되는 피스톤 핀 부시입니다. 고강도 합금 소재로 제작되어 극한 환경에서도 뛰어난 내마모성과 내열성을 제공합니다. OEM 규격에 맞춰 정밀 가공되어 완벽한 호환성을 보장합니다.",
            en: "Piston pin bush for marine diesel engines. Made from high-strength alloy materials, providing excellent wear and heat resistance even in extreme conditions. Precision-machined to OEM specifications ensuring perfect compatibility.",
            cn: "适用于船用柴油发动机的活塞销衬套。采用高强度合金材料制造，即使在极端环境下也能提供出色的耐磨性和耐热性。按OEM规格精密加工，确保完美兼容。"
        },
        specs: {
            ko: { "부품번호": "E205250040Z", "브랜드": "OEM", "카테고리": "피스톤 부품", "소재": "고강도 합금", "상태": "신품", "원산지": "한국" },
            en: { "Part Number": "E205250040Z", "Brand": "OEM", "Category": "Piston Parts", "Material": "High-strength Alloy", "Condition": "New", "Origin": "South Korea" },
            cn: { "零件编号": "E205250040Z", "品牌": "OEM", "类别": "活塞零件", "材质": "高强度合金", "状态": "全新", "产地": "韩国" }
        },
        compatibility: {
            ko: ["다양한 해양 디젤 엔진 호환", "상세 호환 정보는 전화 문의"],
            en: ["Compatible with various marine diesel engines", "Contact us for detailed compatibility"],
            cn: ["兼容各种船用柴油发动机", "详细兼容信息请电话咨询"]
        }
    },
    {
        id: 5,
        image: "./parts_image/Daihatsu_DL22.jpg",
        partNo: "DL22",
        price: "2,600",
        name: { ko: "다이하츠 밸브 스템 씰", en: "Daihatsu DL22 Valve Stem Seal", cn: "Daihatsu DL22 气门杆密封" },
        desc: { ko: "DL22 모델 전용", en: "For DL22 Model", cn: "仅限 DL22 型号" },
        brand: "DAIHATSU",
        category: "valve",
        categoryName: { ko: "밸브", en: "Valve", cn: "阀门" },
        detailInfo: {
            ko: "Daihatsu DL22 엔진 전용 밸브 스템 씰입니다. 엔진 오일 누유를 방지하고 최적의 밸브 작동을 보장합니다. 내열성 고무 소재로 제작되어 고온 환경에서도 안정적인 실링 성능을 유지합니다.",
            en: "Valve stem seal exclusively for Daihatsu DL22 engines. Prevents engine oil leakage and ensures optimal valve operation. Made from heat-resistant rubber material, maintaining stable sealing performance even in high-temperature environments.",
            cn: "Daihatsu DL22发动机专用气门杆密封。防止发动机漏油，确保最佳阀门运行。采用耐热橡胶材料制造，即使在高温环境下也能保持稳定的密封性能。"
        },
        specs: {
            ko: { "부품번호": "DL22", "브랜드": "DAIHATSU", "카테고리": "밸브 부품", "호환 엔진": "DL22, DL-22 시리즈", "상태": "신품", "원산지": "일본" },
            en: { "Part Number": "DL22", "Brand": "DAIHATSU", "Category": "Valve Parts", "Compatible Engine": "DL22, DL-22 Series", "Condition": "New", "Origin": "Japan" },
            cn: { "零件编号": "DL22", "品牌": "DAIHATSU", "类别": "阀门零件", "兼容发动机": "DL22, DL-22 系列", "状态": "全新", "产地": "日本" }
        },
        compatibility: {
            ko: ["Daihatsu DL22", "Daihatsu DL-22 시리즈"],
            en: ["Daihatsu DL22", "Daihatsu DL-22 Series"],
            cn: ["Daihatsu DL22", "Daihatsu DL-22 系列"]
        }
    }
];

// Current products array (will be populated by API or fallback)
let products = [...fallbackProducts];

/**
 * Map DB snake_case row to JS camelCase object.
 */
function mapProductFromAPI(item) {
    return {
        id: item.id,
        image: item.image,
        partNo: item.part_no,
        price: item.price,
        name: item.name,
        desc: item.description,
        brand: item.brand || '',
        category: item.category || '',
        categoryName: item.category_name || {},
        detailInfo: item.detail_info || {},
        specs: item.specs || {},
        compatibility: item.compatibility || {}
    };
}

/**
 * Fetch products from API. Falls back to hardcoded data on failure.
 */
async function fetchProducts() {
    try {
        const response = await fetch(API_BASE + '/api/products');
        if (!response.ok) throw new Error('API response not ok');
        const data = await response.json();
        if (Array.isArray(data) && data.length > 0) {
            products = data.map(mapProductFromAPI);
            console.log(`Loaded ${products.length} products from API`);
        } else {
            console.warn('API returned empty data, using fallback');
            products = [...fallbackProducts];
        }
    } catch (error) {
        console.warn('API fetch failed, using fallback data:', error.message);
        products = [...fallbackProducts];
    }
    return products;
}
