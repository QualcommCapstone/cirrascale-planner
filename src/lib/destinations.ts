/**
 * Curated destinations for the landing hero and the sample-trip cards.
 *
 * Photos are free-licensed Wikipedia lead images, hot-linked from Wikimedia;
 * `credit` is the file page with the author and license. Each prompt matches
 * its photo, so the hero's placeholder text changes with the picture.
 */
export interface Destination {
  place: string;
  region: string;
  prompt: string;
  /** Wikimedia thumbnail path after ".../thumb/", without the "NNNpx-" file prefix. */
  file: string;
  credit: string;
}

const THUMB = "https://upload.wikimedia.org/wikipedia/commons/thumb/";

/** A Wikimedia thumbnail of the destination photo at a standard width. */
export function destinationPhoto(d: Destination, width: 500 | 960 | 1920): string {
  const name = d.file.split("/").pop() as string;
  return `${THUMB}${d.file}/${width}px-${name}`;
}

export const DESTINATIONS: Destination[] = [
  {
    place: "Fushimi Inari",
    region: "Kyoto, Japan",
    prompt: "6 days in Japan for temples, ramen and quiet gardens",
    file: "0/0e/Torii_path_with_lantern_at_Fushimi_Inari_Taisha_Shrine%2C_Kyoto%2C_Japan.jpg",
    credit:
      "https://en.wikipedia.org/wiki/File:Torii_path_with_lantern_at_Fushimi_Inari_Taisha_Shrine,_Kyoto,_Japan.jpg",
  },
  {
    place: "Moraine Lake",
    region: "Banff, Canada",
    prompt: "A week of lakes, hikes and mountain towns in the Canadian Rockies",
    file: "c/c5/Moraine_Lake_17092005.jpg",
    credit: "https://en.wikipedia.org/wiki/File:Moraine_Lake_17092005.jpg",
  },
  {
    place: "Positano",
    region: "Amalfi Coast, Italy",
    prompt: "5 slow days on the Amalfi Coast with seafood and sunsets",
    file: "9/9b/Positano_Sunset.JPG",
    credit: "https://en.wikipedia.org/wiki/File:Positano_Sunset.JPG",
  },
  {
    place: "Machu Picchu",
    region: "Cusco Region, Peru",
    prompt: "8 days in Peru: Lima's food scene, Cusco and Machu Picchu",
    file: "b/bb/Machu_Picchu%2C_2023_%28012%29.jpg",
    credit: "https://en.wikipedia.org/wiki/File:Machu_Picchu,_2023_(012).jpg",
  },
  {
    place: "Chefchaouen",
    region: "Rif Mountains, Morocco",
    prompt: "A week in Morocco from Marrakesh's souks to the blue city",
    file: "7/7c/Chefchaouen-the-blue-city-of-morocco-with-palm-trees-and-the-mountain-view-in-the-backrgound.jpg",
    credit:
      "https://en.wikipedia.org/wiki/File:Chefchaouen-the-blue-city-of-morocco-with-palm-trees-and-the-mountain-view-in-the-backrgound.jpg",
  },
  {
    place: "Hạ Long Bay",
    region: "Quảng Ninh, Vietnam",
    prompt: "10 days in Vietnam: Hanoi street food, Hạ Long Bay and Hội An",
    file: "7/79/Ha_Long_Bay_in_2019.jpg",
    credit: "https://en.wikipedia.org/wiki/File:Ha_Long_Bay_in_2019.jpg",
  },
];
