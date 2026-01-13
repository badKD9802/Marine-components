// js/data.js 파일

const products = [
    {
        id: 1,
        image: "./parts_image/YANMAR CON BOD BEARING(4TNV98 129900-23600).jpg", 
        partNo: "4TNV98 129900-23600",
        price: "2,000",
        name: { ko: "얀마 커넥팅 로드 베어링", en: "YANMAR CON ROD BEARING", cn: "YANMAR 连杆轴承" },
        desc: { ko: "4TNV98 엔진 호환", en: "Compatible with 4TNV98", cn: "兼容 4TNV98" },
        // 상세페이지용 긴 설명 추가
        detailInfo: {
            ko: "이 제품은 얀마 엔진 정품 호환 베어링입니다. 내구성이 뛰어나며...",
            en: "Genuine compatible bearing for Yanmar engines...",
            cn: "该产品是洋马发动机正品兼容轴承..."
        }
    },
    {
        id: 2,
        image: "./parts_image/YANMAR EY18AL.jpg",
        partNo: "PB1002 / PB1003",
        price: "400,000",
        name: { ko: "마린 디젤 엔진 플린저 베럴", en: "YANMAR EY18AL Plunger", cn: "YANMAR EY18AL 柱塞" },
        desc: { ko: "AL-SERIES / AL-PLUS 모델", en: "AL-SERIES / AL-PLUS", cn: "AL-SERIES / AL-PLUS" },
        detailInfo: {
            ko: "고압 연료 펌프용 플런저입니다.",
            en: "Plunger for high pressure fuel pump.",
            cn: "高压燃油泵柱塞。"
        }
    },
    // ... 나머지 상품들 ...
];