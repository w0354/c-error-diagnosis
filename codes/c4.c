#include <stdio.h>

int main(void) {
    FILE *fp = fopen("nums.txt", "r");
    int x;
    fscanf(fp, "%d", &x);
    printf("%d\n", x);
    fclose(fp);
    return 0;
}
